clean:
	rm -rf *.pyc build/ dist/ smux.py.egg-info/

package: clean
	python3 setup.py sdist bdist_wheel

upload: package
	python3 -m twine upload dist/*

doc:
	pydoc  smux > smux.txt
	sed -i '/^DATA$$/,$$d' smux.txt
