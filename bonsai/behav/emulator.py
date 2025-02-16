import argparse


class Emulator:
    @staticmethod
    def setup_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """
        Add the build command to the parser
        """
        parser.set_defaults(
            func=lambda args: print("This feature is not yet implemented.")
        )
        return parser
