FROM bang5:5000/base_x86

WORKDIR /opt

RUN apt-get install -y python3.8 libpython3.8-dev python3-openssl python3-cffi-backend
RUN python3.8 -m pip install mercurial

RUN python3.8 -m pip install -U pip
COPY requirements.txt ./
RUN python3.8 -m pip install --index-url https://projects.bigasterisk.com/ --extra-index-url https://pypi.org/simple -r requirements.txt
RUN python3.8 -m pip install -U 'https://github.com/drewp/cyclone/archive/python3.zip?v3'
RUN python3.8 -m pip install -U cffi
RUN python3.8 -m pip install 'https://foss.heptapod.net/mercurial/hg-git/-/archive/branch/default/hg-git-branch-default.zip'
RUN groupadd --gid 1000 drewp && useradd --uid 501 --gid 1000 drewp

COPY root-hgrc /root/.hgrc
COPY entrypoint.sh config.yaml hg_status.py index.html ./
COPY dot-ssh/* /root/.ssh/
#USER drewp

ENV TZ=America/Los_Angeles
ENV LANG=en_US.UTF-8

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


CMD ["/bin/sh", "entrypoint.sh"]