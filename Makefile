PREFIX?=/usr/local
GIT_LIBEXEC?=${PREFIX}/libexec/git-core
MANDIR?=${PREFIX}/share/man/man1
BINDIR?=${GIT_LIBEXEC}
OWNER?=root

all:

install: all
	python ./setup.py install
	install -d -m 0755 -o ${OWNER} ${BINDIR}/
	install -m 0755 -o ${OWNER} qnew.py ${BINDIR}/git-qnew
	install -m 0755 -o ${OWNER} qrefresh.py ${BINDIR}/git-qrefresh
	install -m 0755 -o ${OWNER} qpush.py ${BINDIR}/git-qpush
	install -m 0755 -o ${OWNER} qpop.py ${BINDIR}/git-qpop
