import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Your name")
    args = parser.parse_args()
    print(f"TODO: implement. args={args}")


if __name__ == "__main__":
    main()
