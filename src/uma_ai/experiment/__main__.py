import argparse

from .runner import run_suite
from .suite import load_suite


def main():
    parser = argparse.ArgumentParser(description="Menjalankan suite eksperimen dari data/experiment.")
    parser.add_argument("suite", help="suite di data/experiment (mis. report, quick, compare) atau path file JSON")
    parser.add_argument("-i", "--input", help="ganti test case suite (di data/input atau path file JSON)")
    parser.add_argument("-j", "--jobs", type=int, default=1,
                        help="jumlah run paralel (default: 1, durasi paling akurat)")
    parser.add_argument("--only", nargs="+", metavar="NAME", help="hanya jalankan eksperimen dengan nama ini")
    args = parser.parse_args()

    suite = load_suite(args.suite)
    out = run_suite(suite, jobs=args.jobs, only=set(args.only) if args.only else None, input_name=args.input)
    print(f"Finished: {out}")


if __name__ == "__main__":
    main()
