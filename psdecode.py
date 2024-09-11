"""
Script Name: psdecode.py
Author: Justin Lund
Last modified: 05/08/24
Date created: 06/05/23
Version: 1.4

Purpose:
This script is designed to de-obfuscate Powershell code

Dependencies:
- pygments: Used for syntax-highlighted code, for ease of reading
- chardet: Used for detecting the encoding of input files

Usage:
python3 psdecode.py -i obfuscated_powershell.ps1

This will provide you with an interactive menu:
0) Show code sample
1) De-obfuscate PowerShell re-ordering
2) Remove backticks
3) Re-concatenate strings
4) Undo aLtErNaTiNg cApS (Title Case Everything)
5) New lines at semicolons
s) Save code

0 will prompt you as to how many lines of code you want to print to screen.
This is used to check if deobfuscation techniques were successful.

The reason the options are separated and the process isn't 100% automated,
is that the order of techniques applied may need to be changed depending on the code.

Once satisfied with the output, press 's' to save it to a new file.
"""

import re
import argparse
import chardet
from pygments import highlight
from pygments.lexers import PowerShellLexer
from pygments.formatters import TerminalFormatter

# Detect and returns the character encoding of the specified file by reading its first 4096 bytes.
def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        rawdata = file.read(4096)
    result = chardet.detect(rawdata)
    return result['encoding']


# Undo string reordering, ie '{2}{0}{1}'-f'str','ing'some'
def deobfuscate_powershell_reorder(lines):

    #---------- Regex patterns for detecting various parts of the PowerShell formatting ----------#

    # Defines a character set that includes alphanumeric, whitespace, newline, punctuation, and special characters.
    charset = r"\w|\d|\n|\s|,|.|\-|=|/|:|#|_|{|}|\[|\]"

    # Matches PowerShell's format string pattern, capturing the order in which arguments are formatted and the string segments.
    regex_finder = r"\(\"([{\d+}]+)\"\s*-f\s*(['" + charset + "',]+)\)"

    # Captures the numerical positions within the curly braces used in PowerShell format strings to reorder arguments.
    regex_position = r"{(\d+)}"

    # Captures the actual content within single quotes that are to be reordered using the format specified in regex_position.
    regex_content = r"'([" + charset + "]+)'"

    # Matches placeholders used to temporarily hold reordered string segments during the de-obfuscation process.
    regex_placeholder = r"({#subs_\d+})"

    # Matches character codes in the PowerShell script, allowing them to be converted from ASCII codes to actual characters.
    regex_char = r"\[char\](\d+)"

    # Detects and handles concatenations in PowerShell, capturing and allowing replacement of concatenated strings.
    regex_concat = r"\((('|\"[\w|\s|\$]+'|\"\+|.)+)\)"

    # Initialize the list to hold de-obfuscated content
    new_content = []

    # Process each line in the input
    for line in lines:
        content = line
        count_matches = 0  # Track the number of replacements to generate unique placeholders
        occurrences = {}  # Dictionary to track replacements for placeholders

        # Convert ASCII character codes to their respective characters
        matches = re.finditer(regex_char, content, re.IGNORECASE)
        for _, word in enumerate(matches):
            total = word.group()
            letter = int(word.groups()[0], 10)
            content = content.replace(total, "'" + chr(letter) + "'")
            content = content.replace("`", "")

        # Main loop to find and replace the formatted strings using the defined patterns
        while re.search(regex_finder, content, re.IGNORECASE):
            matches = re.finditer(regex_finder, content, re.IGNORECASE)
            for _, word in enumerate(matches):
                
                # Extract positions and contents based on the regex matches
                positions = re.findall(
                    regex_position,
                    word.groups()[0].replace("\n", "").strip(),
                    re.IGNORECASE,
                )
                contents = re.findall(
                    regex_content,
                    word.groups()[1].replace("\n", "").strip(),
                    re.IGNORECASE,
                )
                
                # Reconstruct the string in the correct order using the positions
                if len(positions) == len(contents):
                    out = ""
                    for p in positions:
                        if re.match(regex_placeholder, contents[int(p)]):
                            out += occurrences["'" + contents[int(p)] + "'"]
                        else:
                            out += contents[int(p)].strip()
                    
                    # Replace the matched pattern with a placeholder and store the reordered string
                    placeholder = "'{#subs_" + str(count_matches) + "}'"
                    occurrences[placeholder] = out
                    content = content.replace(word.group(), placeholder)
                    count_matches += 1

        # Replace all placeholders with their actual values
        subs = re.finditer(regex_placeholder, content, re.IGNORECASE)
        for _, word in enumerate(subs):
            content = content.replace(
                "'" + word.group() + "'", occurrences["'" + word.group() + "'"]
            )
        
        # Append the processed line to the list of new content
        new_content.append(content)

    # Return the list of de-obfuscated lines
    return new_content


# Remove PowerShell backticks (`) used for line continuation, except at the end of a line.
def remove_ticks(line):
    line = line[:-1].replace('`', '') + line[-1]
    return line


# Replace concatenated string literals in a line with a single string by removing the '+' operator.
def concatenate(line):
    # Define a regex pattern to identify and capture concatenated string literals
    # This pattern identifies two quoted strings separated by a '+'
    pattern = r"((['\"])([^\2]+)\2\s*\+\s*(['\"])([^\4]+)\4)"

    # Search for the first occurrence of concatenated strings in the line
    match = re.search(pattern, line)

    # Continuously search and replace concatenated strings until none are found
    while match:
        # Construct the full string by combining the two parts found in the match
        full_string = match.group(3) + match.group(5)

        # Replace the concatenated part in the line with the full string inside the same type of quotes
        line = line.replace(match.group(), match.group(2) + full_string + match.group(2))

        # Search again to see if there are more concatenations to process
        match = re.search(pattern, line)

    # Return the modified line without any string concatenations
    return line


# Converts all words in a line to title case for standardization, useful for correcting aLtErNaTiNg cApS for improving readability.
def title_case_line(line):
    def title_case_word(match):
        word = match.group(0)
        return word.title()
    return re.sub(r'\b[a-zA-Z0-9_:]+\b', title_case_word, line)

# Apply title case conversion to each line to entire script
def title_case_script(lines):
    return [title_case_line(line) for line in lines]


# Replace semicolons with new lines
def add_new_lines_at_semicolons(lines):
    new_lines = []
    for line in lines:
        new_lines.extend(line.replace(';', ';\n').split('\n')) # Add the newline character right after the semicolon
    return [line + '\n' for line in new_lines if line]  # Ensure every line ends with a newline character


# Main function to run interactive de-obfuscation menu
def main():
    parser = argparse.ArgumentParser(description='De-obfuscates PowerShell scripts.')
    parser.add_argument('-i', '--input', help='The input PowerShell script file.')
    args = parser.parse_args()

    # Exit if no input file is provided
    if args.input is None:
        print("No input file provided. Please provide an input file with the -i option.")
        return

    # Detect the encoding of the input file
    encoding_used = detect_encoding(args.input)
    # print(f"Using detected encoding: {encoding_used}")  # DEBUGGING - Uncomment to print encoding detection

    # Read the file with the detected encoding
    with open(args.input, 'r', encoding=encoding_used) as f:
        lines = f.readlines()

    # Interactive menu loop
    while True:
        print()
        print("0) Show code sample")
        print("1) De-obfuscate PowerShell re-ordering")
        print("2) Remove backticks")
        print("3) Re-concatenate strings")
        print("4) Undo aLtErNaTiNg cApS (Title Case Everything)")
        print("5) New lines at semicolons")
        print("s) Save code")
        print("q) Quit")

        option = input("Choose an option: ").lower()

        if option == "0":
            num_lines = int(input("How many lines of the script would you like to print? "))
            code_to_print = ''.join(lines[:num_lines])
            print(highlight(code_to_print, PowerShellLexer(), TerminalFormatter()))

        elif option == "1":
            lines = deobfuscate_powershell_reorder(lines)
        elif option == "2":
            lines = [remove_ticks(line) for line in lines]
        elif option == "3":
            lines = [concatenate(line) for line in lines]
        elif option == "4":
            lines = title_case_script(lines)
        elif option == "5":
            lines = add_new_lines_at_semicolons(lines)
        elif option == "s":
            output_file = input("Enter the output file name: ")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            break
        elif option == "q":
            break
        else:
            print("Invalid option, please try again.")

# Ensure the script can run standalone
if __name__ == "__main__":
    main()
