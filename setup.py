from setuptools import find_packages, setup

setup(
    name='trading-bot',
    version='0.1.0',
    description='MT5-focused multi-symbol trading bot scanner with hard-stop trade controls.',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    include_package_data=True,
    install_requires=['numpy', 'pandas', 'PyYAML'],
    python_requires='>=3.10',
)
