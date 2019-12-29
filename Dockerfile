FROM python
ADD ./requirements.txt .
RUN pip install -r requirements.txt
RUN mkdir cache
ADD ./sessions-now.py .
CMD ./sessions-now.py
