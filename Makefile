run: install
	octoprint serve
	@echo "Run Called"

install: .install

.install: octoprint_translatemodel/src/translate.cpp setup.py
	octoprint dev plugin:install
	@touch .install
	@echo "Install called"

clean:
	rm .install
	rm *.so
