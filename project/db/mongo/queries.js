// Run with mongosh on the heritage database.
const atlas = db.getSiblingDB("heritage");
const demoId = new ObjectId().toString();
atlas.guides.insertOne({_id: demoId, name_ar: "مرشد للاختبار", languages:["ar"]});
printjson(atlas.guides.findOne({_id: demoId}));
atlas.guides.updateOne({_id: demoId}, {$addToSet:{languages:"en"}});
atlas.guides.deleteOne({_id: demoId});
printjson(atlas.sites.aggregate([
  {$match:{city_id:"00000000-0000-0000-0000-0000000f4241", tags:"عمارة", languages:"ar"}},
  {$lookup:{from:"tours",localField:"_id",foreignField:"site_ids",as:"offers"}},
  {$project:{name_ar:1,tours:{$size:"$offers"}}}, {$sort:{tours:-1,_id:1}}
]).toArray());
