all: build
	sudo docker run -v `pwd`/cache:/tmp/cache -p 5000:5000 -ti d33tah/c3sessions

build:
	sudo docker build -t d33tah/c3sessions .
