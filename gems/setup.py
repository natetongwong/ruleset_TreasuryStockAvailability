from setuptools import setup, find_packages
packages_to_include = find_packages(exclude = ['test.*', 'test', 'test_manual'])
setup(
    name = 'westpacbusiness_rulesettreasurystockavailability',
    version = '1.5',
    packages = packages_to_include,
    description = '',
    install_requires = [],
    data_files = ["resources/extensions.idx"]
)
