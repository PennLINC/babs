install:
	./tests/e2e-slurm/install-babs.sh

setup-user:
	./tests/e2e-slurm/setup-user.sh

e2e: clean
	./tests/e2e-slurm/main.sh

clean:
	@ podman stop slurm 2>/dev/null || true
	@ podman rm slurm 2>/dev/null || true
	@[ -e .testdata/babs_test_project/toybidsapp-container ] && \
		datalad remove -d .testdata/babs_test_project/toybidsapp-container --reckless kill || :
	rm -rf .testdata
