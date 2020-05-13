#!/usr/bin/env python
# coding: utf-8

# In[2]:


from numpy.random import permutation


# In[4]:


res = []
# get the constraints
on_dur = '3'
off_dur = '45'
random_channels = 'ABCDEFGHIJLMNOPQRSTU'
num_puffs = 1
# separate channels into two lists based on what panel they belong
rc_1 = []
rc_2 = []
for v in random_channels:
    if v > 'K':
        rc_2.append(v)
    else:
        rc_1.append(v)
# permute the channel string
if rc_1 and rc_2:
    num_panels = 2
else:
    num_panels = 1
for i in range(int(num_puffs)):
    if i > 0 and num_panels > 1:
        res.append('#')
    channel_permute_1 = permutation(list(rc_1))
    channel_permute_2 = permutation(list(rc_2))
    for v in channel_permute_1:
        res.append('Z' + off_dur + '_' + v + on_dur)
    if num_panels > 1:
        res.append('#')  # the symbol respresents switch panel
    for v in channel_permute_2:
        res.append('Z' + off_dur + '_' + v + on_dur)
res.append('Z' + off_dur)
print('_'.join(res))


# In[ ]:
