# VBulletinVideoCrawler
A crawler that extracts Youtube URLs from a vBulletin thread, 
creates a playlist and insert all the videos in it

It uses a local MongoDB database called "vBulletin". 
This database contains the following collections:
- video_threads: the data about the threads we want to parse.
  ```
    {
        "id":"8142569",
        "last_post":"page=67#post381229258",
        "playlist_title":"Some title for my playlist",
        "playlist_id":"...",
        "last_mod_date":"2020-09-18T14:07:15+02:00"
  }
  ```
  "id" is the thread id in vBulletin URLs. "playlist_id" is the identifier of the playlist in youtube
- pending_videos is generated by the crawler when it can't upload more videos because the API quota has ended
- playlists_created is also generated by the crawler. It stores the videos already uploaded to the
playlists so it can check for duplicates without using quota.
  

TODO list:
- Add new threads to the watch list