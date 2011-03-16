# This script will look up all your running EC2 images, find the current one, and back it up by creating an AMI 
import re
import datetime
from boto.ec2.connection import EC2Connection
from collections import defaultdict
import ConfigParser

import utils
from utils import resolveIp

# Configuration
config = ConfigParser.ConfigParser()
config.read('backup.cfg')

accessKeyId = config.get('AWS', 'accessKeyId')
accessKeySecret = config.get('AWS', 'accessKeySecret')

target = config.get('TARGET', 'target')
number_of_backups_to_keep = int(config.get('TARGET', 'number_of_backups_to_keep'))
backup_interval_hours = int(config.get('TARGET', 'backup_interval_hours'))

def get_my_amis(conn):
    return conn.get_all_images(None, "self", None, None)


def find_target(target, reservations) :
    ip = utils.resolveIp(target)
    print "Finding instance for " + target + " (IP " + ip + ")"
    for reservation in reservations:
        # pdb.set_trace()
        instances = reservation.instances
        if len(instances) != 1:
            print "Skipping reservation " + reservation
            continue
        instance = instances[0]
        instanceIp = resolveIp(instance.dns_name)
        if instanceIp == ip:
            return instance

    raise Exception("Can't find instance with IP " + ip)


def delete_ami_and_snapshot(conn, ami_and_snapshot):
    print "Deleting AMI with ID", ami_and_snapshot['ami'].id
    conn.deregister_image(ami_and_snapshot['ami'].id)
    print "Deleting snapshot with ID", ami_and_snapshot['snapshot_id']
    conn.delete_snapshot(ami_and_snapshot['snapshot_id'])
    return None


def list_to_dict(lst):
    # http://stackoverflow.com/questions/1233546/python-converting-list-of-tuples-into-a-dictionary
    dict = defaultdict( list )

    for key, value in lst:
        if key in dict:
            raise Exception("Key {} found multiple times in list {)".format(key, lst))
        dict[key] = value
    return dict


def delete_oldest_backups(conn, backups_to_keep, backup_description):
    """
    delete_oldest_backups(boto.ec2.connection.EC2Connection, int, string)
    """

    my_amis = get_my_amis(conn)
    my_amis = [x for x in my_amis if x.description == backup_description and len(x.block_device_mapping) == 1]
    def get_snapshot_id(ami):
        return utils.single(ami.block_device_mapping).snapshot_id

    snapshot_ids = [get_snapshot_id(ami) for ami in my_amis]

    # my_amis = filter(lambda x : x.description == backup_description, my_amis)
    # mapped = map(lambda ami: single_or_none(ami.block_device_mapping), my_amis)
    #filtered = filter(lambda item: item is not None, mapped)
    #snapshot_ids = map(lambda device_mapping : device_mapping.snapshot_id, filtered)
    snapshots = conn.get_all_snapshots(snapshot_ids = snapshot_ids)
    snapshots_by_id = list_to_dict(map(lambda snapshot : [snapshot.id, snapshot], snapshots))

    amis_and_snapshots = []
    for ami in my_amis:
        snapshot_id = get_snapshot_id(ami)
        snapshot = snapshots_by_id[snapshot_id]
        amis_and_snapshots.append(
                {'snapshot_id' : snapshot_id,
                 'snapshot' : snapshot,
                 'ami' : ami,
                 'date' : utils.get_time(snapshot.start_time)})

    #def sorter(key1, key2):
#        return key1['date'] < key2['date']

    amis_and_snapshots.sort(key = lambda item : item['date'])

    if len(amis_and_snapshots) <= backups_to_keep:
        print "Got {}/{} backups, nothing to trim".format(len(amis_and_snapshots), backups_to_keep)
        return
    
    for i in range(len(amis_and_snapshots) - backups_to_keep):
        delete_ami_and_snapshot(conn, amis_and_snapshots[i])


def get_snapshots(conn, instance):
    volume = utils.single(instance.block_device_mapping)
    print "Found volume with ID {}".format(volume.volume_id)
    my_snapshots = conn.get_all_snapshots([], "self", None, None)
    return my_snapshots


def find_hours_since_last_backup(conn, instance):
    my_snapshots = get_snapshots(conn, instance)

    if not my_snapshots:
        return None
    latest_snapshot = max(my_snapshots, key=lambda item:utils.get_time(item.start_time))

    latest_time = utils.get_time(latest_snapshot.start_time)
    now_utc = utils.get_current_utc_time()
    diff = now_utc - latest_time
    diff_hours = diff.seconds / 3600
    print "Latest snapshot is from {}, which is {} hours ago".format(latest_time, diff_hours)
    return diff_hours

def main():
    print "Connecting to EC2"
    conn = EC2Connection(accessKeyId, accessKeySecret)
    print "Connected to EC2"

    reservations = conn.get_all_instances()
    instance = find_target(target, reservations)
    hours_since_last_backup = find_hours_since_last_backup(conn, instance)
    if hours_since_last_backup and hours_since_last_backup < backup_interval_hours:
        print "Only {} hours passed since last backup, waiting until {} pass".format(hours_since_last_backup, backup_interval_hours)
        return

    backup_name = target + "_" + re.sub("[: .]", "-", str(datetime.datetime.now()))

    print "Backing up instance '{}' with id '{}' - snapshot {} will be created".format(instance, instance.id, backup_name)

    target_description = "Backup of " + target
    # TODO
    conn.create_image(instance.id, backup_name, target_description, True)

    delete_oldest_backups(conn, number_of_backups_to_keep, target_description)
    print "Done"

main()