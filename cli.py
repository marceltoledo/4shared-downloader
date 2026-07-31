"""
Headless/scripted entry point — preserves the original script's interactive
review-then-run flow (y/N per account with existing history, auto-queue for
brand-new accounts), built on the same app.core modules the web app uses.
Useful for a cron job or a quick terminal session that doesn't need a running
web server.

Usage: python cli.py
"""

import asyncio
import logging

from app import config
from app.core.accounts import read_accounts
from app.core.crawler import run_account
from app.core.history import load_history, history_path
from app.logging_setup import configure_logging

log = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()

    if not config.ACCOUNTS_FILE.exists():
        log.error(f"'{config.ACCOUNTS_FILE}' not found. Create it with one folder URL per line.")
        return

    accounts = read_accounts(config.ACCOUNTS_FILE, config.HISTORY_DIR)
    if not accounts:
        log.error(f"No URLs found in {config.ACCOUNTS_FILE}")
        return

    log.info(f"Loaded {len(accounts)} unique account URL(s)")

    print("\n" + "=" * 60)
    print("  ACCOUNT REVIEW — answer all questions before downloading")
    print("=" * 60)

    accounts_to_run = []
    for i, account in enumerate(accounts, 1):
        print(f"\n  Account {i} [{account.folder_id}]: {account.url}")

        if account.history_count > 0:
            print(f"  History: {account.history_count} file(s) previously downloaded")
            print("  (Only NEW files will be fetched — history entries are")
            print("   strictly skipped even if deleted from disk)")
            answer = input("  Run this account? (y/N): ").strip().lower()
            if answer == "y":
                accounts_to_run.append(account)
                print("  -> Queued")
            else:
                print("  -> Skipped")
        else:
            print("  No history found — new account, will download everything.")
            accounts_to_run.append(account)

    print("\n" + "=" * 60)

    if not accounts_to_run:
        print("  Nothing to do. Exiting.")
        return

    print(f"  Running {len(accounts_to_run)} account(s)")
    print("=" * 60 + "\n")

    for account in accounts_to_run:
        dest_dir = config.DOWNLOAD_DIR / account.folder_id
        downloaded = load_history(config.HISTORY_DIR, account.folder_id)

        log.info(f"\n{'='*60}")
        log.info(f"[Account {account.folder_id}] {account.url}")
        log.info(f"  Download folder : {dest_dir}")
        log.info(f"  History file    : {history_path(config.HISTORY_DIR, account.folder_id)}")
        log.info(f"  Already seen    : {len(downloaded)} file(s) — strictly skipped")
        log.info(f"{'='*60}")

        try:
            await run_account(account.url, dest_dir, account.folder_id, config.HISTORY_DIR,
                               downloaded, config.METADATA_FILE)
        except Exception as e:
            log.error(f"[Account {account.folder_id}] Fatal error, skipping to next account: {e}")

    log.info("\nAll done! Check download_log.txt for details.")


if __name__ == "__main__":
    asyncio.run(main())
