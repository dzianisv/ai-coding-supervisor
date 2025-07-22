
import subprocess
import time

def type_and_enter(text):
    # Activate the target application (e.g., Terminal, or the specific app)
    subprocess.run(['osascript', '-e', 'tell application "Terminal" to activate'])
    # Type the text
    subprocess.run(['osascript', '-e', f'tell application "System Events" to keystroke "{text}"'])
    time.sleep(0.1) # Small delay
    # Press Enter
    subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke return'])

if __name__ == "__main__":
    print("Attempting to type 'continue' and press Enter...")
    type_and_enter("Reflect on the results. Are you sure the task is done correctly? Should we take another approach? Continue.")
    print("Done.")
