#!/usr/bin/env python3
import argparse
from pathlib import Path

import antlr4

from mxc.frontend.parser.MxLexer import MxLexer
from mxc.frontend.parser.MxParser import MxParser
from mxc.frontend.semantic.syntax_checker import SyntaxChecker
from mxc.frontend.semantic.syntax_error import MxSyntaxError, ThrowingErrorListener


class SyntaxTester:
    def __init__(self, testcases_dir='testcases/sema', verbose=False, continue_on_fail=False):
        self.testcases_dir = Path(testcases_dir)
        self.verbose = verbose
        self.continue_on_fail = continue_on_fail

    def check_syntax(self, file_path: str):
        input_stream = antlr4.FileStream(file_path, encoding='utf-8')
        lexer = MxLexer(input_stream)
        parser = MxParser(antlr4.CommonTokenStream(lexer))

        # Attach error listeners
        error_listener = ThrowingErrorListener()
        lexer.removeErrorListeners()
        lexer.addErrorListener(error_listener)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)

        try:
            tree = parser.file_Input()
            checker = SyntaxChecker()
            checker.visit(tree)
            return True, ""
        except MxSyntaxError as e:
            return False, str(e)

    def parse_verdict_and_comment(self, file_path):
        verdict = None
        comment = None
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('Verdict:'):
                    verdict = line.split(':')[-1].strip() == 'Success'
                if line.startswith('Comment:'):
                    comment = line.split(':')[-1].strip()
        if verdict is None:
            raise ValueError(f'Verdict line not found in {file_path}')
        return verdict, comment

    def log_result(self, message):
        print(message)

    def log_verbose(self, message):
        if self.verbose:
            print(message)

    def test_file(self, file_path):
        expected_pass, verdict_comment = self.parse_verdict_and_comment(file_path)
        log_message = ""
        try:
            actual_pass, error_message = self.check_syntax(file_path)
            test_pass = actual_pass == expected_pass
            if test_pass:
                log_message += f"PASSED: {file_path}"
            else:
                log_message += f"FAILED: {file_path} | Expected: {expected_pass}, Got: {actual_pass}"
            if error_message:
                log_message += f" | Error: {error_message}"
        except Exception as e:
            # import traceback
            # traceback.print_exc()
            log_message += f"FAILED: {file_path} | Unexpected error: {e}"
            test_pass = False
        if verdict_comment:
            log_message += f" | Comment: {verdict_comment}"

        if test_pass:
            self.log_verbose(log_message)
            return True
        else:
            self.log_result(log_message)
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
        else:
            self.log_result(f"Some test cases failed in directory: {directory_path}")
        return all_passed

    def run_tests(self, path):
        if path:
            path = self.testcases_dir / Path(path)
            if path.is_file() and path.suffix == '.mx':
                self.test_file(path)
            elif path.is_dir():
                self.test_directory(path)
        else:
            path = self.testcases_dir
            for subdir in path.iterdir():
                if subdir.is_dir():
                    self.test_directory(subdir)

def main():
    parser = argparse.ArgumentParser(description="MxLang Syntax Checker Test Script")
    parser.add_argument('target', nargs='?', default='',
                        help='File or directory to test, e.g. array-package/array-1.mx ')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output, log every test result')
    parser.add_argument('--continue-on-fail', action='store_true', help='Continue testing even if a test fails')
    args = parser.parse_args()

    tester = SyntaxTester(testcases_dir='../../testcases/sema', verbose=args.verbose, continue_on_fail=args.continue_on_fail)
    tester.run_tests(args.target)

if __name__ == "__main__":
    main()
