import argparse
import os
import sys
from ftplib import FTP


def parse_args():
    """Parses custom command line arguments manually to get multiple commands."""
    autoexec_cmds = []
    if "--autoexec" in sys.argv:
        try:
            idx = sys.argv.index("--autoexec")
            raw_string = sys.argv[idx + 1]
            autoexec_cmds = [cmd.strip() for cmd in raw_string.split(";") if cmd.strip()]
        except IndexError:
            print("Warning: --autoexec flag found but no commands were provided.")
    return autoexec_cmds


def resolve_ftp_settings():
    """Resolve FTP settings from CLI args, env vars, or defaults without prompting at import time."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", "--ip", dest="host", default=os.environ.get("FTP_HOST", "192.168.178.176"))
    parser.add_argument("--user", dest="user", default=os.environ.get("FTP_USER", ""))
    parser.add_argument("--pass", "--password", dest="password", default=os.environ.get("FTP_PASS", ""))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FTP_PORT", "5000")))
    known_args, _ = parser.parse_known_args()

    return {
        "host": known_args.host,
        "user": known_args.user,
        "password": known_args.password,
        "port": known_args.port,
    }


FTP_SETTINGS = resolve_ftp_settings()
FTP_HOST = FTP_SETTINGS["host"]
FTP_USER = FTP_SETTINGS["user"]
FTP_PASS = FTP_SETTINGS["password"]
FTP_PORT = FTP_SETTINGS["port"]


def display_file_list(ftp_instance):
    """Fetches and displays the current directory contents with details."""
    print(f"\nCurrent Remote Directory: {ftp_instance.pwd()}")
    print("-" * 80)
    print(f"{'Permissions':<12} {'Links/Owner':<12} {'Group':<10} {'Size (Bytes)':<12} {'Modified Date':<15} {'Name'}")
    print("-" * 80)

    lines = []
    ftp_instance.dir(lines.append)
    for line in lines:
        print(line)
    print("-" * 80)


def handle_command(choice, ftp):
    """Processes a single string command input."""
    if not choice:
        return True

    parts = choice.split(" ", 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "exit":
        print("toodles!")
        return False

    elif cmd == "ls":
        display_file_list(ftp)

    elif cmd == "cd":
        if arg:
            try:
                ftp.cwd(arg)
                print(f"Changed directory to: {ftp.pwd()}")
            except Exception as e:
                print(f"Error changing directory: {e}")
        else:
            print("Usage: cd <folder_name> (or 'cd ..' to go back)")

    elif cmd == "get":
        if arg:
            print(f"Downloading '{arg}'...")
            try:
                with open(arg, "wb") as f_local:
                    ftp.retrbinary(f"RETR {arg}", f_local.write)
                print("Success! Saved to current local directory.")
            except Exception as e:
                print(f"Download failed: {e}")
        else:
            print("Usage: get <filename.nds>")

    elif cmd == "put":
        if arg:
            if os.path.exists(arg):
                print(f"Uploading '{arg}'...")
                try:
                    with open(arg, "rb") as f_local:
                        ftp.storbinary(f"STOR {arg}", f_local)
                    print("Upload successful!")
                except Exception as e:
                    print(f"Upload failed: {e}")
            else:
                print(f"Local file '{arg}' not found.")
        else:
            print("Usage: put <local_filename>")
    else:
        print(f"Unknown command: '{cmd}'")
    return True


def main():
    autoexec_cmds = parse_args()

    try:
        print(f"Connecting to ftp://{FTP_HOST}:{FTP_PORT}...")
        ftp = FTP()
        ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=30)

        with ftp:
            ftp.login(user=FTP_USER, passwd=FTP_PASS)
            print("Login successful!")

            if autoexec_cmds:
                print(f"\n--- Running [AUTOEXEC] Sequence ({len(autoexec_cmds)} commands) ---")
                for command in autoexec_cmds:
                    print(f">> Executing: {command}")
                    if not handle_command(command, ftp):
                        return
                print("--- [AUTOEXEC] Sequence Finished ---\n")
            else:
                display_file_list(ftp)

            while True:
                print("\nAvailable Commands: [cd <folder>] [get <file>] [put <file>] [ls] [exit]")
                try:
                    choice = input("FTP> ").strip()
                except KeyboardInterrupt:
                    print("\nExiting...")
                    break

                if not handle_command(choice, ftp):
                    break

    except KeyboardInterrupt:
        print("\nSetup cancelled by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
