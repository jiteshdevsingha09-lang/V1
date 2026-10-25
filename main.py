# language: Python, file: main.py
# entry point — argparse, CLI flags, launch crawler

import argparse
import sys

from config import TARGET_CHAIN, THREADS, LOG_FILE
from crawler import run_crawler


def main():
    parser = argparse.ArgumentParser(
        description="LLM-guided wallet key crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py --chain BTC --context "my old mining wallet password had my dog name and a year" --words "rex rocky buddy"
  python main.py --chain ETH --context "passphrase was birthday and school name"
  python main.py --chain BTC --context "bitcoin related passphrase" --words "satoshi genesis block"
  python main.py --chain BTC --context "test" --rounds 5
        """
    )
    parser.add_argument("--chain", default="BTC", choices=["BTC", "ETH"],
                        help="blockchain to check (default: BTC)")
    parser.add_argument("--context", required=True,
                        help="context/hints about the passphrase")
    parser.add_argument("--words", nargs="*", default=[],
                        help="known seed words or fragments")
    parser.add_argument("--threads", type=int, default=THREADS,
                        help=f"worker threads (default: {THREADS})")
    parser.add_argument("--rounds", type=int, default=0,
                        help="max generation rounds (0 = unlimited)")
    parser.add_argument("--log", type=str, default=LOG_FILE,
                        help=f"output log file (default: {LOG_FILE})")

    args = parser.parse_args()

    # override config from CLI
    import config
    config.TARGET_CHAIN = args.chain
    config.THREADS = args.threads
    config.LOG_FILE = args.log

    # also patch crawler module references
    import crawler
    crawler.THREADS = args.threads
    crawler.LOG_FILE = args.log
    crawler.TARGET_CHAIN = args.chain

    print(f"[*] wallet key crawler")
    print(f"    chain: {args.chain} | threads: {args.threads} | log: {args.log}")
    print()

    try:
        results = run_crawler(args.context, args.words, args.chain, args.rounds)
        if results:
            print(f"[*] hits: {results}")
        else:
            print("[*] no hits found")
    except KeyboardInterrupt:
        print("\n[!] interrupted — stopping")
        from crawler import stop_crawler
        stop_crawler()
        sys.exit(0)
    except Exception as e:
        print(f"[!] fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()