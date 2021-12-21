"""A computer-readable representation of a rippled.cfg config file."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type


class _Section:
    """
    A computer-readable representation of a section of a rippled.cfg config file.

    e.g.
    [section_name]
    section_key_1=value_1
    section_key_2=value_2
    """

    @classmethod
    def section_header(cls: Type[_Section], line: str) -> Optional[str]:
        """
        If the line is a section header, return the section name. Otherwise return None.

        Args:
            line: The line of the section.
        """
        if line.startswith("[") and line.endswith("]"):
            return line[1:-1]
        return None

    def __init__(self: _Section, name: str) -> None:
        """
        Initialize a section of the config file.

        Args:
            name: The name of the section.
        """
        self._set_init(True)
        self._name = name
        # lines contains all non key-value pairs
        self._lines: List[str] = []
        self._kv_pairs: Dict[str, str] = {}
        self._set_init(False)

    def get_name(self: _Section) -> str:
        return self._name

    def add_line(self: _Section, line: str) -> None:
        s = line.split("=")
        if len(s) == 2:
            self._kv_pairs[s[0].strip()] = s[1].strip()
        else:
            self._lines.append(line)

    def get_lines(self: _Section) -> List[str]:
        return self._lines

    def get_line(self: _Section) -> Optional[str]:
        if len(self._lines) > 0:
            return self._lines[0]
        return None

    def __getstate__(self: _Section) -> Dict[str, Any]:
        return vars(self)

    def __setstate__(self: _Section, state: Dict[str, Any]) -> None:
        vars(self).update(state)

    def _set_init(self: _Section, value: bool) -> None:
        # turn on/off "init" mode
        super().__setattr__("init", value)

    def __getattr__(self: _Section, name: str) -> str:
        try:
            return self._kv_pairs[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self: _Section, name: str, value: str) -> None:
        if self.init or name in self.__dict__:
            super().__setattr__(name, value)
        else:
            self._kv_pairs[name] = value


class ConfigFile:
    """A computer-readable representation of a rippled.cfg config file."""

    def __init__(self: ConfigFile, *, file_name: str) -> None:
        """
        Parse a config file and initialize the ConfigFile object.

        Args:
            file_name: The name/location of the config file.
        """
        # parse the file
        self._file_name = file_name
        self._sections: Dict[str, _Section] = {}

        cur_section = None
        with open(file_name) as f:
            for n, line in enumerate(f):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if section_name := _Section.section_header(line):
                    if cur_section:
                        self._add_section(cur_section)
                    cur_section = _Section(section_name)
                    continue
                if not cur_section:
                    raise ValueError(
                        f"Error parsing config file: {file_name} "
                        f"line_num: {n} line: {line}"
                    )
                cur_section.add_line(line)

        if cur_section:
            self._add_section(cur_section)

    def _add_section(self: ConfigFile, s: _Section) -> None:
        self._sections[s.get_name()] = s

    def get_file_name(self: ConfigFile) -> str:
        """Get the file name/location of the config file."""
        return self._file_name

    def __getstate__(self: ConfigFile) -> Dict[str, Any]:
        """Get the state of a ConfigFile."""
        return vars(self)

    def __setstate__(self: ConfigFile, state: Dict[str, Any]) -> None:
        """
        Set the state of a ConfigFile.

        Args:
            state: The state to update the object with.
        """
        vars(self).update(state)

    def __getattr__(self: ConfigFile, name: str) -> _Section:
        """
        Get a section from the ConfigFile, using the syntax `config_file.section_name`.

        Args:
            name: Name of the section.
        """
        try:
            return self._sections[name]
        except KeyError:
            raise AttributeError(name)
