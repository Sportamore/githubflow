# coding: utf-8
from setuptools import setup, find_packages

setup(
    name='GithubFlow',
    version='1.2.0',

    description='Automated Git-Flow release handling',
    url='https://github.com/carlskeide/githubflow/',
    author='Carl Skeide',

    packages=find_packages(),

    install_requires=[
        "flask",
        "agithub"
    ],
    extras_require={
        'test': [
            'pytest',
            'pytest-cov'
        ],
    }
)
