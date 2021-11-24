"""Python script to convert log files to JSON."""
from __future__ import annotations

import argparse
import json
import re

from slk.utils.eprint import eprint


class LogLine:
    """A computer-readable representation of a line in a log file."""

    UNSTRUCTURED_RE = re.compile(
        r"""(?x)
                # The x flag enables insignificant whitespace mode (allowing comments)
                ^(?P<timestamp>.*UTC)
                [\ ]
                (?P<module>[^:]*):(?P<level>[^\ ]*)
                [\ ]
                (?P<msg>.*$)
                """
    )

    STRUCTURED_RE = re.compile(
        r"""(?x)
                # The x flag enables insignificant whitespace mode (allowing comments)
                ^(?P<timestamp>.*UTC)
                [\ ]
                (?P<module>[^:]*):(?P<level>[^\ ]*)
                [\ ]
                (?P<msg>[^{]*)
                [\ ]
                (?P<json_data>.*$)
                """
    )

    def __init__(self: LogLine, line: str) -> None:
        """
        Initialize a log line.

        Args:
            line: the text of the log line.
        """
        self.raw_line = line
        self.json_data = None

        try:
            if line.endswith("}"):
                m = self.STRUCTURED_RE.match(line)
                if m is not None:
                    self.json_data = json.loads(m.group("json_data"))
                else:
                    m = self.UNSTRUCTURED_RE.match(line)
            else:
                m = self.UNSTRUCTURED_RE.match(line)

            self.timestamp = m.group("timestamp")  # type: ignore
            self.level = m.group("level")  # type: ignore
            self.module = m.group("module")  # type: ignore
            self.msg = m.group("msg")  # type: ignore
        except Exception as e:
            eprint(f"init exception: {e} line: {line}")

    def to_mixed_json(self: LogLine) -> str:
        """return a pretty printed string as mixed json"""
        try:
            r = f"{self.timestamp} {self.module}:{self.level} {self.msg}"
            if self.json_data:
                r += "\n" + json.dumps(self.json_data, indent=1)
            return r
        except:
            eprint(f"Using raw line: {self.raw_line}")
            return self.raw_line

    def to_pure_json(self: LogLine) -> str:
        """return a pretty printed string as pure json"""
        try:
            dict = {}
            dict["t"] = self.timestamp
            dict["m"] = self.module
            dict["l"] = self.level
            dict["msg"] = self.msg
            if self.json_data:
                dict["data"] = self.json_data
            return json.dumps(dict, indent=1)
        except:
            return self.raw_line


def convert_log(
    in_file_name: str, out_file_name: str, *, pure_json: bool = False
) -> None:
    """
    Convert a log file to JSON and dump the result in another file.

    Args:
        in_file_name: The log file to convert.
        out_file_name: The file to dump the result in.
        pure_json: Whether it should be pure JSON or only half (some log info is still
            raw).
    """
    try:
        prev_lines = None
        with open(in_file_name) as input:
            with open(out_file_name, "w") as out:
                for line in input:
                    line = line.strip()
                    if not line:
                        continue
                    if LogLine.UNSTRUCTURED_RE.match(line):
                        if prev_lines:
                            log_line = LogLine(prev_lines)
                            if log_line.module == "SidechainFederator":
                                if pure_json:
                                    print(log_line.to_pure_json(), file=out)
                                else:
                                    print(log_line.to_mixed_json(), file=out)
                        prev_lines = line
                    else:
                        if not prev_lines:
                            eprint(f"Error: Expected prev_lines. Cur line: {line}")
                        assert prev_lines
                        prev_lines += f" {line}"
                if prev_lines:
                    log_line = LogLine(prev_lines)
                    if log_line.module == "SidechainFederator":
                        if pure_json:
                            print(log_line.to_pure_json(), file=out, flush=True)
                        else:
                            print(log_line.to_mixed_json(), file=out, flush=True)
    except Exception as e:
        eprint(f"Exception: {e}")
        raise e


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Python script to convert log files to JSON.")
    )

    parser.add_argument(
        "--input",
        "-i",
        help=("input log file"),
    )

    parser.add_argument(
        "--output",
        "-o",
        help=("output log file"),
    )

    return parser.parse_known_args()[0]


if __name__ == "__main__":
    args = _parse_args()
    convert_log(args.input, args.output, pure_json=True)
