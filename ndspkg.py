from ftplib import FTP
import ftpbackend as ftpserver  # <--- This imports your program!

def main():
    putfile = input("enter file/map u wanna transfer: ")
    # 1. Connect to your DSi / Server
    ftp = FTP()
    ftp.connect(host="192.168.178.176", port=5000)
    ftp.login(user="", passwd="")
    
    print("--- Successfully Connected! ---")

    # 2. Use your program's 'handle_command' function to navigate
    ftpserver.handle_command(f"put {putfile}", ftp)

    # 3. Use your program's 'display_file_list' function to show files
    ftpserver.display_file_list(ftp)

    # 4. Safely close connection
    ftp.quit()
    print("\nDone!")

if __name__ == "__main__":
    main()
