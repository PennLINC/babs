# toybidsapp, multi-ses toy BIDS data
## 12/7/22: iteratively run `babs-submit` and `babs-status` until finished
```
(mydatalad) babs@cubic-sattertt1:code$ pwd
/cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/code
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                 NaN             NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
2  sub-01  ses-C          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
3  sub-02  ses-A          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
4  sub-02  ses-B          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False       NaN                        NaN

Job status:
There are in total of 6 jobs to complete.
1 job(s) have been submitted; 5 job(s) haven't been submitted.
Among submitted jobs,
1 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-submit --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --job sub-02 ses-B
Will only submit specified jobs...
Job for sub-02, ses-B has been submitted (job ID: 2857485).
   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                 NaN             NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
2  sub-01  ses-C          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
3  sub-02  ses-A          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
4  sub-02  ses-B           True  2857485                 NaN             NaN       NaN    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False       NaN                        NaN
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B          False       -1                NaN            NaN       NaN    False       NaN                        NaN
2  sub-01  ses-C          False       -1                NaN            NaN       NaN    False       NaN                        NaN
3  sub-02  ses-A          False       -1                NaN            NaN       NaN    False       NaN                        NaN
4  sub-02  ses-B           True  2857485            pending             qw       NaN    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D          False       -1                NaN            NaN       NaN    False       NaN                        NaN

Job status:
There are in total of 6 jobs to complete.
2 job(s) have been submitted; 4 job(s) haven't been submitted.
Among submitted jobs,
1 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-submit --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --count 2
Job for sub-01, ses-B has been submitted (job ID: 2857486).
Job for sub-01, ses-C has been submitted (job ID: 2857487).
   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486                NaN            NaN       NaN    False       NaN  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487                NaN            NaN       NaN    False       NaN  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A          False       -1                NaN            NaN       NaN    False       NaN                        NaN
4  sub-02  ses-B           True  2857485            pending             qw       NaN    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D          False       -1                NaN            NaN       NaN    False       NaN                        NaN
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486            pending             qw       NaN    False       NaN  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487            pending             qw       NaN    False       NaN  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A          False       -1                NaN            NaN       NaN    False       NaN                        NaN
4  sub-02  ses-B           True  2857485            pending             qw       NaN    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D          False       -1                NaN            NaN       NaN    False       NaN                        NaN

Job status:
There are in total of 6 jobs to complete.
4 job(s) have been submitted; 2 job(s) haven't been submitted.
Among submitted jobs,
1 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-submit --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --all
Job for sub-02, ses-A has been submitted (job ID: 2857488).
Job for sub-02, ses-D has been submitted (job ID: 2857489).
   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486            pending             qw       NaN    False       NaN  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487            pending             qw       NaN    False       NaN  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857488                NaN            NaN       NaN    False       NaN  toy_sub-02_ses-A.*2857488
4  sub-02  ses-B           True  2857485            pending             qw       NaN    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857489                NaN            NaN       NaN    False       NaN  toy_sub-02_ses-D.*2857489
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code        duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN             NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486            running              r  0:00:38.502596    False       NaN  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487            running              r  0:00:38.525145    False       NaN  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857488            pending             qw             NaN    False       NaN  toy_sub-02_ses-A.*2857488
4  sub-02  ses-B           True  2857485            running              r  0:00:38.568529    False       NaN  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857489            pending             qw             NaN    False       NaN  toy_sub-02_ses-D.*2857489

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
1 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --resubmit pending
Resubmit job for sub-02, ses-A, as it was pending and resubmit was requested.
Job for sub-02, ses-A has been submitted (job ID: 2857490).
Resubmit job for sub-02, ses-D, as it was pending and resubmit was requested.
Job for sub-02, ses-D has been submitted (job ID: 2857491).

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN      NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486                NaN            NaN      NaN     True     False  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487                NaN            NaN      NaN     True     False  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857490                NaN            NaN      NaN    False       NaN  toy_sub-02_ses-A.*2857490
4  sub-02  ses-B           True  2857485                NaN            NaN      NaN     True     False  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857491                NaN            NaN      NaN    False       NaN  toy_sub-02_ses-D.*2857491

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
4 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN       NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486                NaN            NaN       NaN     True     False  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487                NaN            NaN       NaN     True     False  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857490            pending             qw       NaN    False       NaN  toy_sub-02_ses-A.*2857490
4  sub-02  ses-B           True  2857485                NaN            NaN       NaN     True     False  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857491            pending             qw       NaN    False       NaN  toy_sub-02_ses-D.*2857491

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
4 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code        duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN             NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486                NaN            NaN             NaN     True     False  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487                NaN            NaN             NaN     True     False  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857490            running              r  0:00:25.899728    False       NaN  toy_sub-02_ses-A.*2857490
4  sub-02  ses-B           True  2857485                NaN            NaN             NaN     True     False  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857491            running              r  0:00:25.925881    False       NaN  toy_sub-02_ses-D.*2857491

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
4 job(s) are successfully finished;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:code$ babs-status --project-root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code duration  is_done is_failed               log_filename
0  sub-01  ses-A           True  2855356                NaN            NaN      NaN     True     False  toy_sub-01_ses-A.*2855356
1  sub-01  ses-B           True  2857486                NaN            NaN      NaN     True     False  toy_sub-01_ses-B.*2857486
2  sub-01  ses-C           True  2857487                NaN            NaN      NaN     True     False  toy_sub-01_ses-C.*2857487
3  sub-02  ses-A           True  2857490                NaN            NaN      NaN     True     False  toy_sub-02_ses-A.*2857490
4  sub-02  ses-B           True  2857485                NaN            NaN      NaN     True     False  toy_sub-02_ses-B.*2857485
5  sub-02  ses-D           True  2857491                NaN            NaN      NaN     True     False  toy_sub-02_ses-D.*2857491

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
6 job(s) are successfully finished;
All jobs are completed!
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
```

## 12/13/22, to show new columns `last_line_o_file` and `alert_message`:
```
(mydatalad) babs@cubic-sattertt1:logs$ babs-submit  \
> --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp \
> --count 1
Job for sub-01, ses-C has been submitted (job ID: 2944712).
   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  \
0  sub-01  ses-A           True  2937181                 NaN             NaN   
1  sub-01  ses-B           True  2944708                 NaN             NaN   
2  sub-01  ses-C           True  2944712                 NaN             NaN   
3  sub-02  ses-A          False       -1                 NaN             NaN   
4  sub-02  ses-B          False       -1                 NaN             NaN   
5  sub-02  ses-D          False       -1                 NaN             NaN   

   duration  is_done is_failed               log_filename last_line_o_file  \
0       NaN     True     False  toy_sub-01_ses-A.*2937181          SUCCESS   
1       NaN     True     False  toy_sub-01_ses-B.*2944708          SUCCESS   
2       NaN    False       NaN  toy_sub-01_ses-C.*2944712              NaN   
3       NaN    False       NaN                        NaN              NaN   
4       NaN    False       NaN                        NaN              NaN   
5       NaN    False       NaN                        NaN              NaN   

                                       alert_message  
0  BABS: Did not find alerting keywords in log fi...  
1  BABS: Did not find alerting keywords in log fi...  
2                                                NaN  
3                                                NaN  
4                                                NaN  
5                                                NaN  
(mydatalad) babs@cubic-sattertt1:logs$ babs-status  \
> --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp \
> --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  \
0  sub-01  ses-A           True  2937181                NaN            NaN   
1  sub-01  ses-B           True  2944708                NaN            NaN   
2  sub-01  ses-C           True  2944712            pending             qw   
3  sub-02  ses-A          False       -1                NaN            NaN   
4  sub-02  ses-B          False       -1                NaN            NaN   
5  sub-02  ses-D          False       -1                NaN            NaN   

   duration  is_done is_failed               log_filename last_line_o_file  \
0       NaN     True     False  toy_sub-01_ses-A.*2937181          SUCCESS   
1       NaN     True     False  toy_sub-01_ses-B.*2944708          SUCCESS   
2       NaN    False       NaN  toy_sub-01_ses-C.*2944712              NaN   
3       NaN    False       NaN                        NaN              NaN   
4       NaN    False       NaN                        NaN              NaN   
5       NaN    False       NaN                        NaN              NaN   

                                       alert_message  
0  BABS: Did not find alerting keywords in log fi...  
1  BABS: Did not find alerting keywords in log fi...  
2                                                NaN  
3                                                NaN  
4                                                NaN  
5                                                NaN  

Job status:
There are in total of 6 jobs to complete.
3 job(s) have been submitted; 3 job(s) haven't been submitted.
Among submitted jobs,
2 job(s) are successfully finished;
1 job(s) are pending;
0 job(s) are running;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:logs$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  \
0  sub-01  ses-A           True  2937181                NaN            NaN   
1  sub-01  ses-B           True  2944708                NaN            NaN   
2  sub-01  ses-C           True  2944712            running              r   
3  sub-02  ses-A          False       -1                NaN            NaN   
4  sub-02  ses-B          False       -1                NaN            NaN   
5  sub-02  ses-D          False       -1                NaN            NaN   

         duration  is_done is_failed               log_filename  \
0             NaN     True     False  toy_sub-01_ses-A.*2937181   
1             NaN     True     False  toy_sub-01_ses-B.*2944708   
2  0:00:01.481231    False       NaN  toy_sub-01_ses-C.*2944712   
3             NaN    False       NaN                        NaN   
4             NaN    False       NaN                        NaN   
5             NaN    False       NaN                        NaN   

  last_line_o_file                                      alert_message  
0          SUCCESS  BABS: Did not find alerting keywords in log fi...  
1          SUCCESS  BABS: Did not find alerting keywords in log fi...  
2              NaN      BABS: No alerting keyword found in log files.  
3              NaN                                                NaN  
4              NaN                                                NaN  
5              NaN                                                NaN  

Job status:
There are in total of 6 jobs to complete.
3 job(s) have been submitted; 3 job(s) haven't been submitted.
Among submitted jobs,
2 job(s) are successfully finished;
0 job(s) are pending;
1 job(s) are running;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:logs$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  \
0  sub-01  ses-A           True  2937181                NaN            NaN   
1  sub-01  ses-B           True  2944708                NaN            NaN   
2  sub-01  ses-C           True  2944712            running              r   
3  sub-02  ses-A          False       -1                NaN            NaN   
4  sub-02  ses-B          False       -1                NaN            NaN   
5  sub-02  ses-D          False       -1                NaN            NaN   

         duration  is_done is_failed               log_filename  \
0             NaN     True     False  toy_sub-01_ses-A.*2937181   
1             NaN     True     False  toy_sub-01_ses-B.*2944708   
2  0:00:25.366269    False       NaN  toy_sub-01_ses-C.*2944712   
3             NaN    False       NaN                        NaN   
4             NaN    False       NaN                        NaN   
5             NaN    False       NaN                        NaN   

  last_line_o_file                                      alert_message  
0          SUCCESS  BABS: Did not find alerting keywords in log fi...  
1          SUCCESS  BABS: Did not find alerting keywords in log fi...  
2  install (ok: 1)      BABS: No alerting keyword found in log files.  
3              NaN                                                NaN  
4              NaN                                                NaN  
5              NaN                                                NaN  

Job status:
There are in total of 6 jobs to complete.
3 job(s) have been submitted; 3 job(s) haven't been submitted.
Among submitted jobs,
2 job(s) are successfully finished;
0 job(s) are pending;
1 job(s) are running;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:logs$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id job_state_category job_state_code  \
0  sub-01  ses-A           True  2937181                NaN            NaN   
1  sub-01  ses-B           True  2944708                NaN            NaN   
2  sub-01  ses-C           True  2944712                NaN            NaN   
3  sub-02  ses-A          False       -1                NaN            NaN   
4  sub-02  ses-B          False       -1                NaN            NaN   
5  sub-02  ses-D          False       -1                NaN            NaN   

  duration  is_done is_failed               log_filename  \
0      NaN     True     False  toy_sub-01_ses-A.*2937181   
1      NaN     True     False  toy_sub-01_ses-B.*2944708   
2      NaN     True     False  toy_sub-01_ses-C.*2944712   
3      NaN    False       NaN                        NaN   
4      NaN    False       NaN                        NaN   
5      NaN    False       NaN                        NaN   

           last_line_o_file                                      alert_message  
0                   SUCCESS  BABS: Did not find alerting keywords in log fi...  
1                   SUCCESS  BABS: Did not find alerting keywords in log fi...  
2  job-2944712-sub-01-ses-C      BABS: No alerting keyword found in log files.  
3                       NaN                                                NaN  
4                       NaN                                                NaN  
5                       NaN                                                NaN  

Job status:
There are in total of 6 jobs to complete.
3 job(s) have been submitted; 3 job(s) haven't been submitted.
Among submitted jobs,
3 job(s) are successfully finished;
0 job(s) are pending;
0 job(s) are running;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
(mydatalad) babs@cubic-sattertt1:logs$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  \
0  sub-01  ses-A           True  2937181                 NaN             NaN   
1  sub-01  ses-B           True  2944708                 NaN             NaN   
2  sub-01  ses-C           True  2944712                 NaN             NaN   
3  sub-02  ses-A          False       -1                 NaN             NaN   
4  sub-02  ses-B          False       -1                 NaN             NaN   
5  sub-02  ses-D          False       -1                 NaN             NaN   

   duration  is_done is_failed               log_filename  \
0       NaN     True     False  toy_sub-01_ses-A.*2937181   
1       NaN     True     False  toy_sub-01_ses-B.*2944708   
2       NaN     True     False  toy_sub-01_ses-C.*2944712   
3       NaN    False       NaN                        NaN   
4       NaN    False       NaN                        NaN   
5       NaN    False       NaN                        NaN   

           last_line_o_file                                      alert_message  
0                   SUCCESS  BABS: Did not find alerting keywords in log fi...  
1                   SUCCESS  BABS: Did not find alerting keywords in log fi...  
2  job-2944712-sub-01-ses-C      BABS: No alerting keyword found in log files.  
3                       NaN                                                NaN  
4                       NaN                                                NaN  
5                       NaN                                                NaN  

Job status:
There are in total of 6 jobs to complete.
3 job(s) have been submitted; 3 job(s) haven't been submitted.
Among submitted jobs,
3 job(s) are successfully finished;
0 job(s) are pending;
0 job(s) are running;
0 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
```

## 12/15/22, test if error in running: got by `qacct`:
I've set `-l h_rt=0:0:20`, i.e., the job can only be run for 20sec, which leads to definite failure.

```
$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml --job-account
Did not request any flags of resubmit.
'--job-account' was requested; babs-status may take longer time...

   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  \
0  sub-01  ses-A           True  2937181                 NaN             NaN   
1  sub-01  ses-B           True  2944708                 NaN             NaN   
2  sub-01  ses-C           True  2944712                 NaN             NaN   
3  sub-02  ses-A           True  2956370                 NaN             NaN   
4  sub-02  ses-B           True  2959899                 NaN             NaN   
5  sub-02  ses-D           True  2960898                 NaN             NaN   

   duration  is_done  is_failed               log_filename  \
0       NaN     True      False  toy_sub-01_ses-A.*2937181   
1       NaN     True      False  toy_sub-01_ses-B.*2944708   
2       NaN     True      False  toy_sub-01_ses-C.*2944712   
3       NaN     True      False  toy_sub-02_ses-A.*2956370   
4       NaN     True      False  toy_sub-02_ses-B.*2959899   
5       NaN    False       True  toy_sub-02_ses-D.*2960898   

                                    last_line_o_file  \
0                                            SUCCESS   
1                                            SUCCESS   
2                                            SUCCESS   
3                                            SUCCESS   
4                                            SUCCESS   
5  I'm in /cbica/projects/BABS/data/test_babs_mul...   

                                       alert_message  
0         BABS: No alert keyword found in log files.  
1         BABS: No alert keyword found in log files.  
2         BABS: No alert keyword found in log files.  
3         BABS: No alert keyword found in log files.  
4         BABS: No alert keyword found in log files.  
5  qacct: failed: 37  : qmaster enforced h_rt, h_...  

Job status:
There are in total of 6 jobs to complete.
6 job(s) have been submitted; 0 job(s) haven't been submitted.
Among submitted jobs,
5 job(s) are successfully finished;
0 job(s) are pending;
0 job(s) are running;
1 job(s) have errors.
All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
```

## 12/16/22, add summary for failed jobs + separated 'job_account' as a new column
### if `--job-account` hasn't been called:
```
$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done is_failed  \
0  sub-01  ses-A           True  2968691                 NaN             NaN       NaN     True     False   
1  sub-01  ses-B           True  2976927                 NaN             NaN       NaN     True     False   
2  sub-01  ses-C           True  2976928                 NaN             NaN       NaN     True     False   
3  sub-02  ses-A           True  2976929                 NaN             NaN       NaN     True     False   
4  sub-02  ses-B           True  2983590                 NaN             NaN       NaN    False      True   
5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False       NaN   

                log_filename                                   last_line_o_file  \
0  toy_sub-01_ses-A.*2968691                                            SUCCESS   
1  toy_sub-01_ses-B.*2976927                                            SUCCESS   
2  toy_sub-01_ses-C.*2976928                                            SUCCESS   
3  toy_sub-02_ses-A.*2976929                                            SUCCESS   
4  toy_sub-02_ses-B.*2983590  install(ok): /scratch/babs/SGE_2983590/job-298...   
5                        NaN                                                NaN   

                                alert_message  job_account  
0  BABS: No alert keyword found in log files.          NaN  
1  BABS: No alert keyword found in log files.          NaN  
2  BABS: No alert keyword found in log files.          NaN  
3  BABS: No alert keyword found in log files.          NaN  
4  BABS: No alert keyword found in log files.          NaN  
5                                         NaN          NaN  

Job status:
There are in total of 6 jobs to complete.
5 job(s) have been submitted; 1 job(s) haven't been submitted.
Among submitted jobs,
4 job(s) are successfully finished;
0 job(s) are pending;
0 job(s) are running;
1 job(s) are failed.

Among all failed job(s):
1 job(s) have alert message: 'BABS: No alert keyword found in log files.';

For the failed job(s) that don't have alert keyword in log files, you may use '--job-account' to get more information about why they are failed. Note that '--job-account' may take longer time.

All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
```
^^ Notice the summary report and how it is different from that when `--job-account` has been called (below)


### if `--job-account` has been called:
```
$ babs-status  --project_root /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp --container_config_yaml_file /cbica/projects/BABS/babs/notebooks/example_container_toybidsapp.yaml
Did not request any flags of resubmit.

   sub_id ses_id  has_submitted   job_id  job_state_category  job_state_code  duration  is_done is_failed  \
0  sub-01  ses-A           True  2968691                 NaN             NaN       NaN     True     False   
1  sub-01  ses-B           True  2976927                 NaN             NaN       NaN     True     False   
2  sub-01  ses-C           True  2976928                 NaN             NaN       NaN     True     False   
3  sub-02  ses-A           True  2976929                 NaN             NaN       NaN     True     False   
4  sub-02  ses-B           True  2982993                 NaN             NaN       NaN    False      True   
5  sub-02  ses-D          False       -1                 NaN             NaN       NaN    False       NaN   

                log_filename                                   last_line_o_file  \
0  toy_sub-01_ses-A.*2968691                                            SUCCESS   
1  toy_sub-01_ses-B.*2976927                                            SUCCESS   
2  toy_sub-01_ses-C.*2976928                                            SUCCESS   
3  toy_sub-02_ses-A.*2976929                                            SUCCESS   
4  toy_sub-02_ses-B.*2982993  install(ok): /scratch/babs/SGE_2982993/job-298...   
5                        NaN                                                NaN   

                                alert_message                                        job_account  
0  BABS: No alert keyword found in log files.                                                NaN  
1  BABS: No alert keyword found in log files.                                                NaN  
2  BABS: No alert keyword found in log files.                                                NaN  
3  BABS: No alert keyword found in log files.                                                NaN  
4  BABS: No alert keyword found in log files.  qacct: failed: 37  : qmaster enforced h_rt, h_...  
5                                         NaN                                                NaN  

Job status:
There are in total of 6 jobs to complete.
5 job(s) have been submitted; 1 job(s) haven't been submitted.
Among submitted jobs,
4 job(s) are successfully finished;
0 job(s) are pending;
0 job(s) are running;
1 job(s) are failed.

Among all failed jobs:
1 job(s) have alert message: 'BABS: No alert keyword found in log files.';

Among jobs that are failed and don't have alert keyword in log files:
1 job(s) have job account of: 'qacct: failed: 37  : qmaster enforced h_rt, h_cpu, or h_vmem limit';

All log files are located in folder: /cbica/projects/BABS/data/test_babs_multi-ses_toybidsapp/analysis/logs
```

