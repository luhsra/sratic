from pathlib import Path

import yaml

from .objects import ObjectStore


class ObjectExporter:
    def __init__(self, objects: ObjectStore) -> None:
        self.objects = objects

    def dump(self, target_dir: str | Path) -> None:
        """Destructive Dumping (objects are altered!)!"""
        target_path = Path(target_dir)
        target_path.mkdir(exist_ok=True)

        # 1. Write an Index of all objects that should be exported.
        index = []
        for obj_id, obj in self.objects.objects.items():
            if obj.get("x-exported", True):
                index.append((obj_id, list(obj.get("type") or [])))
        ## Sort by first type or by name
        index = sorted(index, key=lambda x: (len(x[1]) > 0 and x[1][0]) or x[0])

        # 1.1. Bucketize it to buckets of N items
        N = 250
        buckets = [index[i : i + N] for i in range(0, len(index), N)]
        index = {}
        for bucket_id, bucket in enumerate(buckets):
            index[f"objects_{bucket_id}.yml"] = dict(bucket)
        # 1.2 Write Index File
        with (target_path / "index.yml").open("w+") as fd:
            yaml.dump(index, fd, allow_unicode=True)

        # 2. Write out actual objects
        for bucket_id, bucket in index.items():
            objects = [self.objects.objects[obj_id] for obj_id in bucket]
            for obj in objects:
                schema = self.objects.schema_for(obj)
                for field in schema:
                    if schema[field].get("x-exported", True) is False and field in obj:
                        del obj[field]

            with (target_path / bucket_id).open("w+") as fd:
                yaml.dump(objects, fd, allow_unicode=True)
