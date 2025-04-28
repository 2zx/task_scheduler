from setuptools import setup, find_packages

setup(
    name="task-scheduler",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "psycopg2-binary",
        "sshtunnel",
        "python-dotenv",
    ],
    python_requires=">=3.9",
    author="Your Name",
    author_email="your.email@example.com",
    description="Sistema di pianificazione delle attività basato su SCIP",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "task-scheduler=src.run:main",
        ],
    },
)