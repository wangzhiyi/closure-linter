block_stats = [1,1,1,2,3,3,2,3,4,5,5,2,3,1,1,2,3,4,3]

total_block_depth = 0
total_block_count = 0
block_stats_len = len(block_stats)
local_blocks = []
for i in range(block_stats_len):
  block_depth = block_stats[i]
  block_index = i

  if block_index + 1 == block_stats_len:
    if block_depth == 1:
      total_block_depth += block_depth
      total_block_count += 1
    else:
      local_blocks.append(block_depth)
      max_depth = max(local_blocks)
      total_block_depth += max_depth
      total_block_count += 1
      local_blocks = []
  else:
    next_block_depth = block_stats[block_index+1]
    if block_depth == 1 and next_block_depth == 1:
      total_block_depth += block_depth
      total_block_count += 1
    elif next_block_depth != 1:
      local_blocks.append(block_depth)
    elif block_depth != 1 and next_block_depth == 1:
      local_blocks.append(block_depth)
      max_depth = max(local_blocks)
      total_block_depth += max_depth
      total_block_count += 1
      local_blocks = []

print(total_block_depth)
print(total_block_count)