#!/usr/bin/env python3
"""
Master test runner for JustIRC
Runs all test suites and generates coverage report
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """Discover and run all tests"""
    # Discover all tests in the tests directory
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


def run_with_coverage():
    """Run tests with coverage report"""
    try:
        import coverage
        
        # Start coverage
        cov = coverage.Coverage(source=['..'])
        cov.start()
        
        # Run tests
        exit_code = run_all_tests()
        
        # Stop coverage and report
        cov.stop()
        cov.save()
        
        print("\n" + "="*70)
        print("COVERAGE REPORT")
        print("="*70)
        cov.report()
        
        # Generate HTML report
        cov.html_report(directory='htmlcov')
        print(f"\nHTML coverage report generated in: htmlcov/index.html")
        
        return exit_code
        
    except ImportError:
        print("Coverage.py not installed. Running tests without coverage.")
        print("Install with: pip install coverage")
        return run_all_tests()


if __name__ == '__main__':
    # Check if --coverage flag is passed
    if '--coverage' in sys.argv:
        sys.exit(run_with_coverage())
    else:
        sys.exit(run_all_tests())
