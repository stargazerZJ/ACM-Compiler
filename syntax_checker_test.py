#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
from syntax_checker import SyntaxChecker
from syntax_error import MxSyntaxError
import antlr4
from antlr_generated.MxParser import MxParser
from antlr_generated.MxLexer import MxLexer

class SyntaxTester:
    def __init__(self, testcases_dir='testcases/sema', verbose=False, continue_on_fail=False):
        self.testcases_dir = Path(testcases_dir)
        self.verbose = verbose
        self.continue_on_fail = continue_on_fail

    def check_syntax(self, file_path: str):
        input_stream = antlr4.FileStream(file_path)
        lexer = MxLexer(input_stream)
        token_stream = antlr4.CommonTokenStream(lexer)
        parser = MxParser(token_stream)
        tree = parser.file_Input()
        checker = SyntaxChecker()
        try:
            checker.visit(tree)
            return True, ""
        except MxSyntaxError as e:
            return False, str(e)

    def parse_verdict_and_comment(self, file_path):
        verdict = None
        comment = None
        with open(file_path, 'r') as file:
            for line in file:
                if line.startswith('Verdict:'):
                    verdict = line.split(':')[-1].strip() == 'Success'
                if line.startswith('Comment:'):
                    comment = line.split(':')[-1].strip()
        if verdict is None:
            raise ValueError(f'Verdict line not found in {file_path}')
        return verdict, comment

    def log_result(self, message):
        if self.verbose or "FAILED" in message:
            print(message)

    def test_file(self, file_path):
        expected_pass, verdict_comment = self.parse_verdict_and_comment(file_path)
        actual_pass, error_message = self.check_syntax(file_path)

        if actual_pass == expected_pass:
            if self.verbose:
                self.log_result(f"PASSED: {file_path} | Error: {error_message} | Comment: {verdict_comment}")
            return True
        else:
            self.log_result(
                f"FAILED: {file_path} | Expected: {expected_pass}, Got: {actual_pass} | Error: {error_message} | Comment: {verdict_comment}"
            )
            return False

    def test_directory(self, directory_path):
        directory_path = Path(directory_path)
        mx_files = list(directory_path.rglob('*.mx'))

        if not mx_files:
            return

        all_passed = True
        for file in mx_files:
            passed = self.test_file(file)
            if not passed and not self.continue_on_fail:
                return False
            all_passed = all_passed and passed

        if all_passed:
            self.log_result(f"All test cases passed in directory: {directory_path}")
        return all_passed

    def run_tests(self, path):
        path = self.testcases_dir / Path(path)
        if path.is_file() and path.suffix == '.mx':
            self.test_file(path)
        elif path.is_dir():
            self.test_directory(path)
        else:
            for subdir in path.iterdir():
                if subdir.is_dir():
                    self.test_directory(subdir)

def main():
    parser = argparse.ArgumentParser(description="MxLang Syntax Checker Test Script")
    parser.add_argument('target', nargs='?', default='testcases/sema',
                        help='File or directory to test, e.g. array-package/array-1.mx ')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output, log every test result')
    parser.add_argument('--continue-on-fail', action='store_true', help='Continue testing even if a test fails')
    args = parser.parse_args()

    tester = SyntaxTester(testcases_dir='testcases/sema', verbose=args.verbose, continue_on_fail=args.continue_on_fail)
    tester.run_tests(args.target)

if __name__ == "__main__":
    main()
