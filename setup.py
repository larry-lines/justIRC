#!/usr/bin/env python3
"""
Setup script for JustIRC
Build .deb package with: python3 setup.py --command-packages=stdeb.command bdist_deb
"""

from setuptools import setup, find_packages
import os

# Read README for long description
try:
    with open('README.md', 'r', encoding='utf-8') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = "JustIRC - Secure End-to-End Encrypted IRC Client and Server"

# Read requirements
try:
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
except FileNotFoundError:
    requirements = []

setup(
    name='justirc',
    version='1.0.0',
    description='Secure End-to-End Encrypted IRC Client and Server',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='JustIRC Team',
    author_email='',
    url='https://github.com/larry-lines/justIRC',
    license='MIT',
    
    # Package data
    packages=find_packages(),
    py_modules=[
        'server',
        'client',
        'client_gui',
        'crypto_layer',
        'protocol',
        'image_transfer',
        'config_manager',
    ],
    
    # Include non-Python files
    package_data={
        '': ['*.png', '*.md', '*.txt'],
    },
    include_package_data=True,
    
    # Dependencies
    install_requires=requirements,
    
    # Python version requirement
    python_requires='>=3.8',
    
    # Entry points for command-line scripts
    entry_points={
        'console_scripts': [
            'justirc-server=server:main',
            'justirc-cli=client:main',
            'justirc-gui=client_gui:main',
        ],
    },
    
    # Classification
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Communications :: Chat',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS',
    ],
    
    # Keywords
    keywords='irc chat encryption secure e2e messaging',
)
