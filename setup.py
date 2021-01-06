from setuptools import setup


with open('README.md') as f:
    long_description = f.read()

short_description = "Simple tmux launcher that will take less than 2 minutes to learn."

setup(
  name="smux.py",
  version='0.1.19',
  author="Henry Qin",
  author_email="root@hq6.me",
  description=short_description,
  long_description=long_description,
  long_description_content_type='text/markdown',
  platforms=["All platforms that tmux runs on."],
  license="MIT",
  url="https://github.com/hq6/smux",
  py_modules=['smux'],
  scripts=['smux.py']
)
