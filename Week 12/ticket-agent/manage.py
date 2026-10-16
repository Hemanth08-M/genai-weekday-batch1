"""Housekeeping.

    python manage.py seed                       # DESTRUCTIVE: reset tickets to 3 seed tickets
    python manage.py reset --users alice bob    # DESTRUCTIVE: wipe all tickets + those users' Mem0 memories
(Langfuse traces are never touched by these commands.)
"""
import argparse

from ticket_agent.config import check_env


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    reset = sub.add_parser("reset")
    reset.add_argument("--users", nargs="*", default=[], help="user_ids whose Mem0 memories should be deleted")
    args = parser.parse_args()

    check_env()
    from ticket_agent import db, memory

    db.init_db()
    if args.cmd == "seed":
        db.seed_tickets()
        print("Tickets reset to seed data:")
        db.print_tickets()
    else:
        db.wipe_tickets()
        for user in args.users:
            memory.delete_memories(user)
        print(f"Tickets wiped; memories deleted for: {', '.join(args.users) or '(none)'}")


if __name__ == "__main__":
    main()
