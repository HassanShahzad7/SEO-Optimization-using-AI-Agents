import random
from datetime import datetime
now = datetime.now()
import datetime as dt

from scheduler import Scheduler
from scheduler.trigger import Monday, Tuesday

num = random.randint(1,100000)
def foo():
    with open('rend.text','a') as f:
        f.write('{} -your random numer is {}\n'.format(now,num))

schedule = Scheduler()

schedule.minutely(dt.time(second=15), foo)
foo()
print(schedule)


# from crontab import CronTab

# jobScheduler = CronTab(user='root')

# job = jobScheduler.new(command='intro_full_text_metadata.py')

# job.hour.every(1)
# jobScheduler.write()