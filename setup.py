from distutils.core import setup

setup(
    name='destroystack',
    version='0.0.1',
    author='Martina Kollarova',
    author_email='mkollaro@redhat.com',
    url='http://pypi.python.org/pypi/DestroyStack/',
    packages=['destroystack'],
    license='LICENSE',
    description='Test reliability of OpenStack by simulating failures.',
    long_description=open('README.md').read(),
)
