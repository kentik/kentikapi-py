from distutils.core import setup

setup(
    name='kentikapi',
    version='0.1.0',
    author='Blake Caldwell',
    packages=['kentikapi', 'kentikapi.v5'],
    url='https://github.com/kentik/api-client',
    license='LICENSE.txt',
    description='Kentik API Client',
    long_description=open('README.md').read(),
    install_requires=['requests'],
)
