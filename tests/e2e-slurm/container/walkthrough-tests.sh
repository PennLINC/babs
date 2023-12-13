#!/bin/bash -i

set -eu

# add that outside user
# groupadd --gid "$GID" "$USER"  && useradd --uid $UID --gid "$GID" "$USER"

# Install singularity inside the container
yum update -y && yum install -y epel-release &&  yum update -y &&  yum install -y singularity-runtime apptainer
#
# git version
# git config user.name > /dev/null || git config --system user.name "e2e slurm"
# git config user.email > /dev/null || git config --system user.email "fake@example.com"
# git config --system --add safe.directory '*'

export TESTDATA=/opt/testdata
BABS_USER=testuser


# Wait for slurm to be up
max_retries=10
delay=10  # seconds

echo "Try connecting to slurm with sacct until it succeeds"
set +e # We need to check the error code and allow failures until slurm has started up
export PATH=${PWD}/tests/e2e-slurm/bin/:${PATH}
for ((i=1; i<=max_retries; i++)); do
	# Check if the command was successful
	if sacct; then
		echo "Slurm is up and running!"
		break
	else
		echo "Waiting for Slurm to start... retry $i/$max_retries"
		sleep $delay
	fi
	# exit if max retries reached
	if [ $i -eq $max_retries ]; then
		echo "Failed to start Slurm after $max_retries attempts."
	exit 1
    fi
done
set -e

# Currently we are root inside the container. Now we create a user to own the testdata
useradd "$BABS_USER"
# cp rather than use bind directly so it can be owned by the container user and not cause issues outside
mkdir "${TESTDATA}"
cp /opt/outer/* "${TESTDATA}"


# We build the singularity container now while we are root, and use it later as testuser
pushd "${TESTDATA}"
singularity build  \
    toybidsapp-0.0.7.sif \
    docker://pennlinc/toy_bids_app:0.0.7

chown -R "$BABS_USER:$BABS_USER" "${TESTDATA}"
su "${BABS_USER}" "${TESTDATA}/babs-user-script.sh"
