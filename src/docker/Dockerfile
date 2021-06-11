
# Start with Ubuntu 18.04 base image
FROM public.ecr.aws/ubuntu/ubuntu:18.04 as job-controller-build

ENV DEBIAN_FRONTEND="noninteractive"

WORKDIR /app
RUN apt update -y \
    # Install necessary packages via apt-get
    && apt install -y wget zip libreadline7 libgomp1 dumb-init python3 python3-boto3 python3-pip \
    # Install pdb2pqr3 via pip
    && pip3 install pdb2pqr==3.1.0 \
    # Download APBS binary from GitHub release
    && wget https://github.com/Electrostatics/apbs-pdb2pqr/releases/download/vAPBS-3.0.0/APBS-3.0.0_Linux.zip \
    && unzip APBS-3.0.0_Linux.zip \
    && rm APBS-3.0.0_Linux.zip \
    && rm -r APBS-3.0.0.Linux/share/apbs/examples \
    # Cleanup and remove unnecessary packages
    && apt remove zip wget -y \
    && apt autoremove -y \
    && apt autoremove python3-pip -y \
    && apt clean -y

ENV LD_LIBRARY_PATH=/app/APBS-3.0.0.Linux/lib
ENV PATH="${PATH}:/app/APBS-3.0.0.Linux/bin"

COPY  job_control.py /app/
RUN chmod +x /app/job_control.py
WORKDIR /app/run

ENTRYPOINT [ "/usr/bin/dumb-init", "--" ]
CMD [ "/app/job_control.py" ]
