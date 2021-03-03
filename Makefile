run: install
	octoprint serve
	@echo "Run Called"

test: install
	rm -f testfiles/*.translate*
	python3 test.py
	@grep "TRANSLATE-MODEL" testfiles/*.translate*
	@echo "Test Called"

install: .install

.install: octoprint_translatemodel/src/translate.cpp setup.py
	octoprint dev plugin:install
	@touch .install
	@echo "Install called"

clean:
	rm .install
	rm *.so
