from setuptools import setup, find_packages


setup(
    name="beachboys-minecraft-manager",
    version="1.0.0",
    description="A manager for the minecraft server executable",
    author="Zach Shames",
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    classifiers=[
        "Programming Language   ::  Python  ::  3.9",
        "Natural Language   ::  English",
        "License    ::  Other/Proprietary License"
    ],
    entry_points={
        "console_scripts": [
            "beachboys-minecraft-manager=src.cli:execute"
        ]
    },
    zip_safe=False,
    install_requires=["click", "discord"]
)
