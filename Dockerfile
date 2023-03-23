FROM alpine

# set a directory for the app
WORKDIR /usr/src/app

# copy all the files to the container
COPY . .

# install python and pip
RUN apk add --update python3 py3-pip curl

# install curl
RUN apk --no-cache add curl

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# expose flask standard port 
EXPOSE 5000

CMD ["python","./publishSomePeerIPs.py"]
