#Version 0.1
#install.packages(c("DBI","paws","noctua"))

library(DBI)
library(paws)
library(noctua)

con <- dbConnect(noctua::athena(),
                aws_access_key_id='REMOVED',
                aws_secret_access_key='REMOVED',
                s3_staging_dir='s3://path/to/query/bucket/',
                region_name='eu-west-2')

res <- dbExecute(con, "SELECT * FROM test.table LIMIT 10")
dbFetch(res)
#dbClearResult(res)
