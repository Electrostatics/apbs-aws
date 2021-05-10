
FROM public.ecr.aws/j4g5x5m8/pdb2pqr:latest as pdb2pqr-build

# Copy builds to cleaner base
FROM public.ecr.aws/ubuntu/ubuntu:18.04 as pdb2pqr-final
COPY --from=pdb2pqr-build /app/builds /app/builds

WORKDIR /app
RUN apt update -y \
    && apt install -y wget zip libreadline7 libgomp1 tini

RUN wget https://github.com/Electrostatics/apbs-pdb2pqr/releases/download/vAPBS-3.0.0/APBS-3.0.0_Linux.zip \
    && unzip APBS-3.0.0_Linux.zip \
    && rm APBS-3.0.0_Linux.zip \
    && rm -r APBS-3.0.0.Linux/share/apbs/examples

ENV LD_LIBRARY_PATH=/app/APBS-3.0.0.Linux/lib
ENV PATH="${PATH}:/app/APBS-3.0.0.Linux/bin"
ENV PATH="${PATH}:/app/builds/pdb2pqr"

RUN apt update -y \
    && apt install python python-setuptools wget zip libpython2.7 libmaloc-dev python3 python3-boto3 -y \
    # Install numpy for PDB2PKA
    && apt install python-pip -y \
    && wget https://files.pythonhosted.org/packages/3a/5f/47e578b3ae79e2624e205445ab77a1848acdaa2929a00eeef6b16eaaeb20/numpy-1.16.6-cp27-cp27mu-manylinux1_x86_64.whl \
    && pip install numpy-1.16.6-cp27-cp27mu-manylinux1_x86_64.whl \
    # Install networkx for PDB2PKA
    && wget https://files.pythonhosted.org/packages/f3/f4/7e20ef40b118478191cec0b58c3192f822cace858c19505c7670961b76b2/networkx-2.2.zip \
    && unzip networkx-2.2.zip \
    && cd networkx-2.2 \
    && pip install decorator==4.4.2 \
    && python setup.py install \
    && cd .. \
    # Cleanup and remove unnecessary packages
    && rm -r networkx-2.2 networkx-2.2.zip numpy-1.16.6-cp27-cp27mu-manylinux1_x86_64.whl \
    && apt remove zip wget -y \
    && apt autoremove -y \
    && apt autoremove python-pip -y \
    && apt clean -y
    
COPY  job_control.py /app/
RUN chmod +x /app/job_control.py
WORKDIR /app/run

ENTRYPOINT [ "/usr/bin/tini", "--" ]
CMD [ "/app/job_control.py" ]
