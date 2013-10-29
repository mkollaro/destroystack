from setuptools import setup

setup(
    name='destroystack',
    version='0.0.1',
    author='Martina Kollarova',
    author_email='mkollaro@gmail.com',
    url='http://pypi.python.org/pypi/destroystack/',
    packages=['destroystack'],
    license='Apache License, Version 2.0',
    description='Test reliability of OpenStack by simulating failures.',
    long_description=open('README.md').read(),
    install_requires=[
        'nose >= 1.1.2',
        'python-swiftclient >= 1.4.0',
    ],
)
