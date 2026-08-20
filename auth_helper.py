"""
Run this ONCE every trading day to generate access token.
Usage:  python auth_helper.py
"""

import webbrowser
from kiteconnect import KiteConnect
import config


def main():
    kite = KiteConnect(api_key=config.KITE_API_KEY)
    login_url = kite.login_url

    print("=" * 50)
    print("  KITE CONNECT - DAILY AUTHENTICATION")
    print("=" * 50)
    print()
    print("Step 1: Opening login URL in your browser...")
    print(f"If it doesn't open, manually visit:\n{login_url}\n")

    try:
        webbrowser.open(login_url)
    except Exception:
        pass

    print("Step 2: Log in with your Zerodha credentials")
    print("Step 3: After login, you'll be redirected to your callback URL")
    print("Step 4: Copy the 'request_token' from the URL")
    print("        Example URL: https://...?request_token=XXXXXX&action=...")
    print()

    request_token = input("Paste request_token here: ").strip()

    if not request_token:
        print("No token provided. Exiting.")
        return

    try:
        session = kite.generate_session(
            request_token, api_secret=config.KITE_API_SECRET
        )
        access_token = session["access_token"]

        env_path = ".env"
        lines = []
        found = False
        try:
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("KITE_ACCESS_TOKEN="):
                        lines.append(f"KITE_ACCESS_TOKEN={access_token}\n")
                        found = True
                    else:
                        lines.append(line)
        except FileNotFoundError:
            pass

        if not found:
            lines.append(f"KITE_ACCESS_TOKEN={access_token}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

        print()
        print(f"Access token generated: {access_token[:12]}...")
        print("Saved to .env file. You're ready to run the system!")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        print("Check your API secret and try again.")


if __name__ == "__main__":
    main()
