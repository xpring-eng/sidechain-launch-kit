from __future__ import annotations

from typing import Any, Dict, List, Optional, Type


class Section:
    @classmethod
    def section_header(cls: Type[Section], line: str) -> Optional[str]:
        """
        If the line is a section header, return the section name
        otherwise return None
        """
        if line.startswith("[") and line.endswith("]"):
            return line[1:-1]
        return None

    def __init__(self: Section, name: str) -> None:
        self._set_init(True)
        self._name = name
        # lines contains all non key-value pairs
        self._lines: List[str] = []
        self._kv_pairs: Dict[str, str] = {}
        self._set_init(False)

    def get_name(self: Section) -> str:
        return self._name

    def add_line(self: Section, line: str) -> None:
        s = line.split("=")
        if len(s) == 2:
            self._kv_pairs[s[0].strip()] = s[1].strip()
        else:
            self._lines.append(line)

    def get_lines(self: Section) -> List[str]:
        return self._lines

    def get_line(self: Section) -> Optional[str]:
        if len(self._lines) > 0:
            return self._lines[0]
        return None

    def __getstate__(self: Section) -> Dict[str, Any]:
        return vars(self)

    def __setstate__(self: Section, state: Dict[str, Any]) -> None:
        vars(self).update(state)

    def _set_init(self: Section, value: bool) -> None:
        super().__setattr__("init", value)

    def __getattr__(self: Section, name: str) -> str:
        try:
            return self._kv_pairs[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self: Section, name: str, value: str) -> None:
        if self.init or name in self.__dict__:
            super().__setattr__(name, value)
        else:
            self._kv_pairs[name] = value


class ConfigFile:
    def __init__(self: ConfigFile, *, file_name: str) -> None:
        # parse the file
        self._file_name = file_name
        self._sections: Dict[str, Section] = {}

        cur_section = None
        with open(file_name) as f:
            for n, line in enumerate(f):
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if section_name := Section.section_header(line):
                    if cur_section:
                        self.add_section(cur_section)
                    cur_section = Section(section_name)
                    continue
                if not cur_section:
                    raise ValueError(
                        f"Error parsing config file: {file_name} "
                        f"line_num: {n} line: {line}"
                    )
                cur_section.add_line(line)

        if cur_section:
            self.add_section(cur_section)

    def add_section(self: ConfigFile, s: Section) -> None:
        self._sections[s.get_name()] = s

    def get_file_name(self: ConfigFile) -> str:
        return self._file_name

    def __getstate__(self: ConfigFile) -> Dict[str, Any]:
        return vars(self)

    def __setstate__(self: ConfigFile, state: Dict[str, Any]) -> None:
        vars(self).update(state)

    def __getattr__(self: ConfigFile, name: str) -> Section:
        try:
            return self._sections[name]
        except KeyError:
            raise AttributeError(name)
