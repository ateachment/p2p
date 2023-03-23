FROM alpine

# set a directory for the app
WORKDIR /usr/src/app

# copy all the files to the container
COPY . .

# install python, pip, curl 
RUN apk add --update python3 py3-pip curl

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# expose flask standard port 
EXPOSE 5000

CMD ["python","./publishSomePeerIPs.py"]
