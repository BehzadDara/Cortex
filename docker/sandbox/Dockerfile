FROM python:3.12-slim

RUN pip install --no-cache-dir numpy==2.3.3 pandas==2.3.3 matplotlib==3.10.6

ENV MPLBACKEND=Agg \
    MPLCONFIGDIR=/opt/matplotlib \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -c "import matplotlib.pyplot" \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox

COPY supervise.py execute.py /sandbox/

USER sandbox
WORKDIR /workspace

ENTRYPOINT ["python", "/sandbox/supervise.py"]
