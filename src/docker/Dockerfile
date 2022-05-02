
# Start with Ubuntu 18.04 base image
FROM public.ecr.aws/ubuntu/ubuntu:20.04 as job-controller-build

ARG PDB2PQR_VERSION=3.3.0
ARG APBS_VERSION=2.9.0

ENV DEBIAN_FRONTEND="noninteractive"

WORKDIR /app
RUN apt update -y \
    # Install necessary packages via apt-get
    && apt install -y wget zip libreadline7 libgomp1 dumb-init python3 python3-boto3 python3-pip \
    # Install pdb2pqr3 via pip
    && pip3 install pdb2pqr==${PDB2PQR_VERSION} \
    # Download APBS binary from GitHub release
    && wget https://github.com/Electrostatics/apbs/releases/download/v${APBS_VERSION}/APBS-${APBS_VERSION}.Linux.zip \
    && unzip APBS-${APBS_VERSION}.Linux.zip \
    && rm APBS-${APBS_VERSION}.Linux.zip \
    && rm -r APBS-${APBS_VERSION}.Linux/share/apbs/examples \
    # Cleanup and remove unnecessary packages
    && apt remove zip wget -y \
    && apt autoremove -y \
    && apt autoremove python3-pip -y \
    && apt clean -y

ENV LD_LIBRARY_PATH=/app/APBS-${APBS_VERSION}.Linux/lib
ENV PATH="${PATH}:/app/APBS-${APBS_VERSION}.Linux/bin"

COPY  job_control.py /app/
RUN chmod +x /app/job_control.py
WORKDIR /app/run

ENTRYPOINT [ "/usr/bin/dumb-init", "--" ]
CMD [ "/app/job_control.py" ]
