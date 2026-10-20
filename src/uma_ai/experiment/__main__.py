import argparse

from .runner import run_suite
from .suite import load_suite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("suite")
    parser.add_argument("-i", "--input")
    parser.add_argument("-j", "--jobs", type=int, default=1)
    parser.add_argument("--only", nargs="+", metavar="NAME")
    args = parser.parse_args()

    suite = load_suite(args.suite)
    out = run_suite(suite, jobs=args.jobs, only=set(args.only) if args.only else None, input_name=args.input)
    print(f"Finished: {out}")


if __name__ == "__main__":
    main()
