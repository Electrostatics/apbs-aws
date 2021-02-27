
FROM electrostatics/pdb2pqr-bin:latest as pdb2pqr-build

# Copy builds to cleaner base
FROM ubuntu:18.04 as pdb2pqr-final
COPY --from=pdb2pqr-build /app/builds /app/builds

WORKDIR /app
RUN apt update -y \
    && apt install -y wget zip libreadline7 libgomp1

RUN wget https://github.com/Electrostatics/apbs-pdb2pqr/releases/download/vAPBS-3.0.0/APBS-3.0.0_Linux.zip \
    && unzip APBS-3.0.0_Linux.zip \
    && rm APBS-3.0.0_Linux.zip \
    && rm -r APBS-3.0.0.Linux/share/apbs/examples

ENV LD_LIBRARY_PATH=/app/APBS-3.0.0.Linux/lib
ENV PATH="${PATH}:/app/APBS-3.0.0.Linux/bin"

RUN apt update \
    && apt install python python-setuptools wget zip libpython2.7 libmaloc-dev -y \
    # Install networkx for PDB2PKA
    && wget https://files.pythonhosted.org/packages/f3/f4/7e20ef40b118478191cec0b58c3192f822cace858c19505c7670961b76b2/networkx-2.2.zip \
    && unzip networkx-2.2.zip \
    && cd networkx-2.2 \
    && python setup.py install \
    # Cleanup and remove unneeded packages
    && cd .. \
    && rm -r networkx-2.2 networkx-2.2.zip \
    && apt remove zip wget -y \
    && apt autoremove -y \
    && apt clean -y
    
COPY  job_control.py /app/
WORKDIR /app/run

ENTRYPOINT [ "/app/job_control.py" ]
