# Linux OOM Analyser

I've started this project to give the Python to JavaScript compiler 
[Transcrypt](https://www.transcrypt.org/) a try.

This web page splits the content of a Linux Out Of Memory message into 
smaller pieces, aggregates these and presents them in a more human friendly 
format.

You can use the current version on [www.carstengrohmann.de/oom/](https://www.carstengrohmann.de/oom/).


## Design Goals
 * A local copy of the web page should run offline - without an Internet 
   connection, without loading 3rd party libraries nor transferring data to 
   foreign servers
 * A better understanding of the Linux Memory Management
 * Start learning JavaScript, CSS and HTML
 
 
## Requirements
 * [Python](http://www.python.org) 3.6 or later
 * [Transcrypt](https://www.transcrypt.org/) 3.6.53 or later


## Installation
Install Python virtual environment
 
Use the provided Makefile:
    
```
# make venv
```

or setup the virtual environment manually:

```
# virtualenv env
# . env/bin/activate
# env/bin/pip install -Ur requirements.txt
``` 

## Build
Use the provided Makefile:
```
# make venv
```

or build it manually:

```
# . env/bin/activate
# transcrypt --build --map --nomin -e 6 OOMAnalyser.py
```

## Further Information
 * [Transcrypt](https://www.transcrypt.org/).
 * [Linux man pages online](https://man7.org/)
 * [Decoding the Linux kernel's page allocation failure messages](https://utcc.utoronto.ca/~cks/space/blog/linux/DecodingPageAllocFailures)
 * [Linux Kernel OOM Log Analysis](http://elearningmedium.com/linux-kernel-oom-log-analysis/)


## Known Bugs/Issues

Check the bug tracker on [GitHub](https://github.com/CarstenGrohmann/OOMAnalyser/issues) for current open bugs.
New bugs can be reported there also.

## License
```
Copyright (c) 2017 Carsten Grohmann mail <add at here> carsten-grohmann.de

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Enjoy!
Carsten Grohmann
