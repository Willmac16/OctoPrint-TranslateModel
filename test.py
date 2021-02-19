import translate, sys

translate.test(16.5, -12.5)
if len(sys.argv) > 1:
	translate.translate(16.5, -12.5, sys.argv[1])
