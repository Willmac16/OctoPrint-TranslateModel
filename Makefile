run: install
	octoprint serve
	@echo "Run Called"

test: install
	rm -f testfiles/*.translate*
	python3.8 test.py
	@#grep "TRANSLATE-MODEL" testfiles/*.translate*
	@#echo "Test Called"

install: .install

.install: octoprint_translatemodel/src/translate.cpp setup.py
	octoprint dev plugin:install
	@touch .install
	@echo "Install called"

clean:
	rm .install
	rm *.so

send:
	git-scp faker "~/.octoprint/plugins/OctoPrint-TranslateModel" -y
	ssh faker "source ~/oprint/bin/activate && cd ~/.octoprint/plugins/OctoPrint-TranslateModel && make install"
	ssh faker sudo service octoprint restart
	ssh faker tail -f .octoprint/logs/octoprint.log
