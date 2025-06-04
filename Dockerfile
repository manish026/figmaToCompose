FROM python:3.13.3-alpine3.21

WORKDIR /app

RUN apk add --update --no-cache curl

COPY requirements.txt .

RUN python3 -m pip install -r requirements.txt

COPY src src

CMD [ "python3", "src/figma_to_jetpack.py" ]