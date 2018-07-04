# coding: utf-8

import yaml
import os
from collections import defaultdict

class ObjectExporter:
    def __init__(self, objects):
        self.objects = objects

    def dump(self, target_dir):
        """Destructive Dumping (objects are altered!)!"""
        if not os.path.exists(target_dir):
            os.mkdir(target_dir)

        # 1. Write an Index of all objects that should be exported.
        index = []
        for obj_id, obj in self.objects.objects.items():
            if obj.get('x-exported', True):
                index.append( (obj_id, list(obj.get('type'))) )
        ## Sort by first type or by name
        index = list(sorted(index, key= lambda x: (len(x[1]) > 0 and x[1][0]) or x[0]))

        # 1.1. Bucketize it to buckets of N items
        N = 250
        buckets = [index[i:i+N] for i in range(0, len(index), N)]
        index = {}
        for bucket_id, bucket in enumerate(buckets):
            index["objects_%d.yml" % (bucket_id)] = dict(bucket)
        # 1.2 Write Index File
        with open(os.path.join(target_dir, 'index.yml'), 'w+') as fd:
            yaml.dump(index, fd, allow_unicode=True)

        # 2. Write out actual objects
        for bucket_id, bucket in index.items():
            objects = [self.objects.objects[obj_id] for obj_id in bucket]
            for obj in objects:
                schema = self.objects.schema_for(obj)
                for field in schema:
                    if schema[field].get('x-exported', True) is False and field in obj:
                        del obj[field]

            with open(os.path.join(target_dir, bucket_id), 'w+') as fd:
                yaml.dump(objects, fd, allow_unicode=True)
