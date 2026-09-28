"""vera-bot DIR : a bot for the documents in DIR (.txt / .md; sub-folders become sovereigns)."""
import sys


def main():
    import vera_base
    if len(sys.argv) < 2:
        print("usage: vera-bot DOCS_DIR"); sys.exit(1)
    bot = vera_base.Bot.from_dir(sys.argv[1])
    print("%d documents, %d sentences. Ask in Japanese or English (empty line to quit)." % (len(bot.base.docs), len(bot.sents)))
    while True:
        try:
            q = input("> ").strip()
        except EOFError:
            break
        if not q:
            break
        if q.startswith("/judge "):
            print(bot.judge(q[7:]))
        else:
            print(bot.reply(q)["text"])


if __name__ == "__main__":
    main()
